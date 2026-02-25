#!/usr/bin/env python3
"""
Report Editor: Post-generation quality checks and corrections for geotechnical reports.

Two operation modes:
  Mode A (Production): No reference needed. Catches grammar, format, completeness issues.
  Mode B (Development): Uses reference + audit JSON for targeted corrections.

Mode A runs automatically after every report generation.
Mode B is only used during template development with a reference report.

Usage:
    # Mode A: Production check (after every generation)
    python3 -m automation.report_editor \
        reference-material/4001612-bell-lloc/4001612_generated.docx \
        --project-path reference-material/4001612-bell-lloc

    # Mode B: Development check (with reference)
    python3 -m automation.report_editor \
        reference-material/4001612-bell-lloc/4001612_generated.docx \
        --reference reference-material/4001612-bell-lloc/4001612_informe.docx \
        --audit-json reference-material/4001612-bell-lloc/validation/audit_intelligent.json

Output:
    {project_path}/validation/edit_checks.json    (issues found)
    {output_path}                                  (corrected .docx, if --apply)

Author: Eficients.cat
Date: 2026-02-08
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Catalan grammar rules
# ============================================================================

# Catalan articles before vowels/h: "de l'" not "del" or "de la"
# "de l'Arquitectura", "de l'empresa", "de l'habitatge"
CATALAN_VOWELS = set('aàáeèéiíïoòóuúüh')


def check_catalan_articles(text: str) -> list[dict]:
    """
    Check Catalan article/preposition rules.

    Returns list of issues found with suggested fixes.
    """
    issues = []

    # Rule 1: "de el" should be "del" (before consonant) or "de l'" (before vowel)
    for m in re.finditer(r"\bde\s+el\s+(\w)", text, re.IGNORECASE):
        next_char = m.group(1).lower()
        if next_char in CATALAN_VOWELS:
            issues.append({
                'type': 'grammar',
                'rule': 'article_contraction',
                'position': m.start(),
                'original': m.group(0),
                'suggested': f"de l'{m.group(1)}",
                'explanation': "\"de el\" davant vocal → \"de l'\"",
            })
        else:
            issues.append({
                'type': 'grammar',
                'rule': 'article_contraction',
                'position': m.start(),
                'original': m.group(0),
                'suggested': f"del {m.group(1)}",
                'explanation': "\"de el\" → \"del\"",
            })

    # Rule 2: "de la" before vowel/h → "de l'"
    for m in re.finditer(r"\bde\s+la\s+([" + ''.join(CATALAN_VOWELS) + r"]\w*)", text, re.IGNORECASE):
        word = m.group(1)
        issues.append({
            'type': 'grammar',
            'rule': 'article_elision',
            'position': m.start(),
            'original': m.group(0),
            'suggested': f"de l'{word}",
            'explanation': f"\"de la\" davant vocal/h → \"de l'\"",
        })

    # Rule 3: "a el" → "al"
    for m in re.finditer(r"\ba\s+el\s+(\w)", text, re.IGNORECASE):
        next_char = m.group(1).lower()
        if next_char in CATALAN_VOWELS:
            issues.append({
                'type': 'grammar',
                'rule': 'article_contraction',
                'position': m.start(),
                'original': m.group(0),
                'suggested': f"a l'{m.group(1)}",
                'explanation': "\"a el\" davant vocal → \"a l'\"",
            })
        else:
            issues.append({
                'type': 'grammar',
                'rule': 'article_contraction',
                'position': m.start(),
                'original': m.group(0),
                'suggested': f"al {m.group(1)}",
                'explanation': "\"a el\" → \"al\"",
            })

    # Rule 4: "per el" → "pel"
    for m in re.finditer(r"\bper\s+el\s+(\w)", text, re.IGNORECASE):
        issues.append({
            'type': 'grammar',
            'rule': 'article_contraction',
            'position': m.start(),
            'original': m.group(0),
            'suggested': f"pel {m.group(1)}",
            'explanation': "\"per el\" → \"pel\"",
        })

    # Rule 5: Double spaces
    for m in re.finditer(r"  +", text):
        issues.append({
            'type': 'format',
            'rule': 'double_space',
            'position': m.start(),
            'original': m.group(0),
            'suggested': ' ',
            'explanation': 'Espai doble',
        })

    return issues


def check_empty_values(text: str, para_idx: int) -> list[dict]:
    """Check for empty variable placeholders or suspicious patterns."""
    issues = []

    # Leftover Jinja tags (template rendering failed)
    for m in re.finditer(r'\{\{.*?\}\}|\{%.*?%\}', text):
        issues.append({
            'type': 'completeness',
            'rule': 'leftover_jinja',
            'position': m.start(),
            'paragraph_idx': para_idx,
            'original': m.group(0),
            'suggested': '',
            'explanation': 'Tag Jinja no renderitzat — possible error al template o variable buida',
        })

    # Empty parentheses suggesting missing data: "l' ()" or "del  ,"
    for m in re.finditer(r"(?:l'|del?|la)\s*\(\s*\)", text):
        issues.append({
            'type': 'completeness',
            'rule': 'empty_parens',
            'position': m.start(),
            'paragraph_idx': para_idx,
            'original': m.group(0),
            'suggested': '',
            'explanation': 'Parèntesis buits — possiblement una variable sense valor',
        })

    # Consecutive commas or punctuation suggesting missing content
    for m in re.finditer(r'[,;]\s*[,;]', text):
        issues.append({
            'type': 'completeness',
            'rule': 'consecutive_punctuation',
            'position': m.start(),
            'paragraph_idx': para_idx,
            'original': m.group(0),
            'suggested': ',',
            'explanation': 'Puntuació consecutiva — possiblement una variable buida entre elles',
        })

    # "el/la/l' " followed by nothing meaningful (just space+punctuation)
    for m in re.finditer(r"\b(?:el|la|l'|els|les|del|dels)\s+[.,;:)]", text):
        issues.append({
            'type': 'completeness',
            'rule': 'article_without_noun',
            'position': m.start(),
            'paragraph_idx': para_idx,
            'original': m.group(0),
            'suggested': '',
            'explanation': 'Article seguit de puntuació — falta el nom (variable buida?)',
        })

    return issues


def check_number_format(text: str) -> list[dict]:
    """Check number formatting for Catalan conventions."""
    issues = []

    # In Catalan technical docs, decimals use comma (3,18 not 3.18)
    # BUT: some contexts use period (coordinates, etc.)
    # We only flag obvious cases in running text (not in tables or coordinates)

    # Sentence-level numbers with period decimal that should be comma
    # e.g., "La densitat és 2.05 g/cm³" → "La densitat és 2,05 g/cm³"
    # This is tricky — many legitimate uses of period. Skip for now,
    # let Claude Code evaluate these contextually.

    return issues


def check_punctuation(text: str) -> list[dict]:
    """Check punctuation consistency."""
    issues = []

    # Space before punctuation (common typo)
    for m in re.finditer(r'\s+[.,;:!?](?!\d)', text):
        # Exception: don't flag numbers like "1 .000" (thousands separator context)
        issues.append({
            'type': 'format',
            'rule': 'space_before_punctuation',
            'position': m.start(),
            'original': m.group(0),
            'suggested': m.group(0).strip(),
            'explanation': 'Espai abans de puntuació',
        })

    # Missing space after punctuation
    for m in re.finditer(r'[.,;:!?](?!\s|$|\d|["\')])', text):
        # Skip decimals (3.18), abbreviations (S.L.), URLs
        context = text[max(0, m.start()-1):m.end()+1]
        if re.match(r'\d[.,]\d', context):
            continue
        if re.match(r'[A-Z]\.[A-Z]', context):
            continue
        issues.append({
            'type': 'format',
            'rule': 'missing_space_after_punctuation',
            'position': m.start(),
            'original': m.group(0),
            'suggested': m.group(0) + ' ',
            'explanation': 'Falta espai després de puntuació',
        })

    return issues


# ============================================================================
# Document-level checks
# ============================================================================

@dataclass
class EditIssue:
    """A single issue found in the document."""
    paragraph_idx: int
    paragraph_text: str
    issue_type: str  # grammar, format, completeness, consistency
    rule: str
    original: str
    suggested: str
    explanation: str
    severity: str = 'warning'  # info, warning, error
    auto_fixable: bool = True


@dataclass
class EditCheckResult:
    """Result of running all checks on a document."""
    generated_file: str
    check_date: str
    mode: str  # 'production' or 'development'
    issues: list[dict] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)


def run_production_checks(generated_path: Path, project_path: Path | None = None,
                          user_data_path: Path | None = None) -> EditCheckResult:
    """
    Mode A: Production checks — no reference needed.

    Checks:
    1. Catalan grammar (articles, contractions)
    2. Empty/missing variable values
    3. Punctuation consistency
    4. Leftover Jinja tags
    """
    from docx import Document

    if project_path is None:
        project_path = generated_path.parent

    if user_data_path is None:
        candidate = project_path / 'user_data.json'
        if candidate.exists():
            user_data_path = candidate

    doc = Document(str(generated_path))
    result = EditCheckResult(
        generated_file=str(generated_path),
        check_date=datetime.now().isoformat(),
        mode='production',
    )

    all_issues: list[dict] = []

    # Check body paragraphs
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        para_issues = []
        para_issues.extend(check_catalan_articles(text))
        para_issues.extend(check_empty_values(text, idx))
        para_issues.extend(check_punctuation(text))

        for issue in para_issues:
            all_issues.append({
                'paragraph_idx': idx,
                'elem_id': f"p{idx:03d}",
                'paragraph_text': text[:120] + ('...' if len(text) > 120 else ''),
                'issue_type': issue['type'],
                'rule': issue['rule'],
                'original': issue.get('original', ''),
                'suggested': issue.get('suggested', ''),
                'explanation': issue.get('explanation', ''),
                'severity': 'warning',
                'auto_fixable': issue['type'] in ('grammar', 'format'),
            })

    # Check table cells
    table_para_offset = len(doc.paragraphs)
    for table_idx, table in enumerate(doc.tables):
        for row_idx, row in enumerate(table.rows):
            seen_in_row: set[int] = set()
            for col_idx, cell in enumerate(row.cells):
                tc_id = id(cell._tc)
                is_dup = tc_id in seen_in_row
                seen_in_row.add(tc_id)
                for p_local, para in enumerate(cell.paragraphs):
                    text = para.text.strip()
                    # Build elem_id for this table cell
                    t_elem_id = f"t{table_idx}_r{row_idx}_c{col_idx}"
                    if p_local > 0:
                        t_elem_id += f"_p{p_local}"
                    if not text or len(text) < 5:
                        table_para_offset += 1
                        continue
                    para_issues = []
                    para_issues.extend(check_catalan_articles(text))
                    para_issues.extend(check_empty_values(text, table_para_offset))
                    for issue in para_issues:
                        all_issues.append({
                            'paragraph_idx': table_para_offset,
                            'elem_id': t_elem_id,
                            'paragraph_text': text[:120] + ('...' if len(text) > 120 else ''),
                            'issue_type': issue['type'],
                            'rule': issue['rule'],
                            'original': issue.get('original', ''),
                            'suggested': issue.get('suggested', ''),
                            'explanation': issue.get('explanation', ''),
                            'severity': 'warning',
                            'auto_fixable': issue['type'] in ('grammar', 'format'),
                        })
                    table_para_offset += 1

    result.issues = all_issues

    # Statistics
    by_type = {}
    by_rule = {}
    auto_fixable = 0
    for issue in all_issues:
        t = issue['issue_type']
        by_type[t] = by_type.get(t, 0) + 1
        r = issue['rule']
        by_rule[r] = by_rule.get(r, 0) + 1
        if issue['auto_fixable']:
            auto_fixable += 1

    result.statistics = {
        'total_issues': len(all_issues),
        'by_type': by_type,
        'by_rule': by_rule,
        'auto_fixable': auto_fixable,
        'needs_review': len(all_issues) - auto_fixable,
    }

    return result


def run_development_checks(
    generated_path: Path,
    reference_path: Path,
    audit_json_path: Path | None = None,
    project_path: Path | None = None,
) -> EditCheckResult:
    """
    Mode B: Development checks — with reference report.

    Adds reference-based corrections on top of production checks.
    Only usable when a known-good reference exists (e.g., Bell-Lloc).
    """
    if project_path is None:
        project_path = generated_path.parent

    # Start with production checks
    result = run_production_checks(generated_path, project_path)
    result.mode = 'development'

    # Load audit JSON if available
    if audit_json_path is None:
        candidate = project_path / 'validation' / 'audit_intelligent.json'
        if candidate.exists():
            audit_json_path = candidate

    if audit_json_path and audit_json_path.exists():
        with open(audit_json_path, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)

        # Add issues from audit for paragraphs with LLM classifications
        for para in audit_data.get('dynamic_paragraphs', []):
            llm_class = para.get('llm_classification', '')
            if llm_class in ('DADES_ERRÒNIES', 'TEMPLATE_ERROR'):
                result.issues.append({
                    'paragraph_idx': para['idx'],
                    'elem_id': para.get('elem_id', f"p{para['idx']:03d}"),
                    'paragraph_text': para.get('generated_text', '')[:120],
                    'issue_type': 'audit',
                    'rule': f'audit_{llm_class.lower()}',
                    'original': para.get('generated_text', ''),
                    'suggested': para.get('suggested_fix', ''),
                    'explanation': para.get('llm_explanation', ''),
                    'severity': 'error',
                    'auto_fixable': False,
                })

        # Add missing paragraphs
        for para in audit_data.get('missing_in_generated', []):
            result.issues.append({
                'paragraph_idx': -1,
                'elem_id': para.get('elem_id', f"ref_{para.get('ref_idx', 0):03d}"),
                'paragraph_text': para.get('reference_text', '')[:120],
                'issue_type': 'audit',
                'rule': 'missing_paragraph',
                'original': '',
                'suggested': para.get('reference_text', ''),
                'explanation': 'Paràgraf present a la referència però absent al generat',
                'severity': 'error',
                'auto_fixable': False,
            })

    # Update statistics
    by_type = {}
    by_rule = {}
    auto_fixable = 0
    for issue in result.issues:
        t = issue['issue_type']
        by_type[t] = by_type.get(t, 0) + 1
        r = issue['rule']
        by_rule[r] = by_rule.get(r, 0) + 1
        if issue['auto_fixable']:
            auto_fixable += 1

    result.statistics = {
        'total_issues': len(result.issues),
        'by_type': by_type,
        'by_rule': by_rule,
        'auto_fixable': auto_fixable,
        'needs_review': len(result.issues) - auto_fixable,
    }

    return result


def apply_fixes(generated_path: Path, issues: list[dict], output_path: Path) -> dict:
    """
    Apply auto-fixable corrections to a .docx file.

    Only applies issues where auto_fixable=True.
    Returns changelog dict.

    IMPORTANT Zero Fabrication rules:
    - Only fix grammar/format (articles, punctuation, spacing)
    - NEVER change technical data, numbers, names, addresses
    - NEVER add content not present in the original
    """
    from docx import Document

    doc = Document(str(generated_path))
    changelog = []
    fixes_applied = 0

    # Group issues by paragraph index for efficient processing
    issues_by_para = {}
    for issue in issues:
        if not issue.get('auto_fixable', False):
            continue
        idx = issue['paragraph_idx']
        if idx not in issues_by_para:
            issues_by_para[idx] = []
        issues_by_para[idx].append(issue)

    # Apply fixes to body paragraphs
    for idx, para in enumerate(doc.paragraphs):
        if idx not in issues_by_para:
            continue
        text = para.text
        new_text = text
        for issue in issues_by_para[idx]:
            original = issue['original']
            suggested = issue['suggested']
            if original and suggested and original in new_text:
                new_text = new_text.replace(original, suggested, 1)
                changelog.append({
                    'paragraph_idx': idx,
                    'elem_id': issue.get('elem_id', f"p{idx:03d}"),
                    'rule': issue['rule'],
                    'original': original,
                    'applied': suggested,
                    'explanation': issue['explanation'],
                })
                fixes_applied += 1

        # Apply text changes while preserving formatting
        if new_text != text:
            _replace_paragraph_text(para, new_text)

    # Save corrected document
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))

    return {
        'fixes_applied': fixes_applied,
        'output_file': str(output_path),
        'changelog': changelog,
    }


def _replace_paragraph_text(paragraph, new_text: str):
    """
    Replace paragraph text while trying to preserve run formatting.

    Strategy: If paragraph has a single run, just replace its text.
    If multiple runs, concatenate into first run and clear the rest.
    This preserves the formatting of the first run.
    """
    runs = paragraph.runs
    if not runs:
        return

    if len(runs) == 1:
        runs[0].text = new_text
    else:
        # Put all text in first run, clear others
        runs[0].text = new_text
        for run in runs[1:]:
            run.text = ''


def run_checks(
    generated_path: Path,
    reference_path: Path | None = None,
    audit_json_path: Path | None = None,
    project_path: Path | None = None,
    user_data_path: Path | None = None,
    output_json_path: Path | None = None,
    apply: bool = False,
    output_docx_path: Path | None = None,
) -> dict:
    """
    Main entry point: run checks and optionally apply fixes.

    Args:
        generated_path: Path to generated .docx
        reference_path: Path to reference .docx (Mode B only)
        audit_json_path: Path to audit_intelligent.json (Mode B only)
        project_path: Project folder path
        user_data_path: Path to user_data.json
        output_json_path: Where to save check results JSON
        apply: Whether to apply auto-fixable corrections
        output_docx_path: Where to save corrected .docx (requires apply=True)
    """
    if project_path is None:
        project_path = generated_path.parent

    if output_json_path is None:
        output_json_path = project_path / 'validation' / 'edit_checks.json'

    # Choose mode
    if reference_path and reference_path.exists():
        print(f"Mode B: Development checks (with reference)")
        result = run_development_checks(generated_path, reference_path, audit_json_path, project_path)
    else:
        print(f"Mode A: Production checks (no reference)")
        result = run_production_checks(generated_path, project_path, user_data_path)

    # Save check results
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    result_dict = {
        'generated_file': result.generated_file,
        'check_date': result.check_date,
        'mode': result.mode,
        'issues': result.issues,
        'statistics': result.statistics,
    }
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    # Print summary
    stats = result.statistics
    print(f"\n{'=' * 60}")
    print(f"EDIT CHECK SUMMARY ({result.mode})")
    print(f"{'=' * 60}")
    print(f"Total issues:      {stats['total_issues']}")
    if stats.get('by_type'):
        for t, count in sorted(stats['by_type'].items()):
            print(f"  {t}: {count}")
    print(f"Auto-fixable:      {stats['auto_fixable']}")
    print(f"Needs review:      {stats['needs_review']}")
    print(f"\nOutput: {output_json_path}")

    # Apply fixes if requested
    changelog_dict = None
    if apply and stats['auto_fixable'] > 0:
        if output_docx_path is None:
            stem = generated_path.stem
            output_docx_path = generated_path.parent / f"{stem}_edited.docx"

        print(f"\nApplying {stats['auto_fixable']} auto-fixable corrections...")
        changelog_dict = apply_fixes(generated_path, result.issues, output_docx_path)
        print(f"Applied: {changelog_dict['fixes_applied']} fixes")
        print(f"Output:  {changelog_dict['output_file']}")

        # Save changelog
        changelog_path = project_path / 'validation' / 'edit_changelog.json'
        with open(changelog_path, 'w', encoding='utf-8') as f:
            json.dump(changelog_dict, f, ensure_ascii=False, indent=2)
        print(f"Changelog: {changelog_path}")

    return result_dict


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Post-generation quality checks for geotechnical reports',
    )
    parser.add_argument('generated', help='Path to generated .docx')
    parser.add_argument('--reference', '-r', help='Path to reference .docx (Mode B)')
    parser.add_argument('--audit-json', '-a', help='Path to audit_intelligent.json (Mode B)')
    parser.add_argument('--project-path', '-p', help='Project folder path')
    parser.add_argument('--user-data', '-u', help='Path to user_data.json')
    parser.add_argument('--output-json', help='Output JSON path for check results')
    parser.add_argument('--apply', action='store_true', help='Apply auto-fixable corrections')
    parser.add_argument('--output-docx', '-o', help='Output .docx path (requires --apply)')

    args = parser.parse_args()

    run_checks(
        generated_path=Path(args.generated),
        reference_path=Path(args.reference) if args.reference else None,
        audit_json_path=Path(args.audit_json) if args.audit_json else None,
        project_path=Path(args.project_path) if args.project_path else None,
        user_data_path=Path(args.user_data) if args.user_data else None,
        output_json_path=Path(args.output_json) if args.output_json else None,
        apply=args.apply,
        output_docx_path=Path(args.output_docx) if args.output_docx else None,
    )


if __name__ == '__main__':
    main()
