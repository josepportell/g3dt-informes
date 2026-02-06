#!/usr/bin/env python3
"""
G3DT Lab Results Extractor

Extracts laboratory test results from digital PDF reports (e.g., LAB-SIG.pdf).
Uses PyMuPDF (fitz) to read text, then regex patterns to extract key values.

Typical lab PDF contents:
- Sample identification (SPT-1, M-1, etc.)
- Test location and depth
- Sulfate content (mg/kg) per UNE 83963:2008
- Granulometry results
- Atterberg limits (if cohesive soils)

Usage:
    from automation.lab_extractor import extract_lab_results

    results = extract_lab_results('/path/to/project')
    print(results['sulfate_mg_kg'])  # 89.8

Author: Eficients.cat
Date: 2026-02-06
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LabTestResult:
    """A single laboratory test result."""
    type: str                    # e.g., "Contingut en sulfats solubles UNE 83963:2008"
    sample_id: str = ''          # e.g., "SPT-1", "M-1"
    location: str = ''           # e.g., "S-1", "DPSH-1"
    depth: str = ''              # e.g., "-1.00 a -1.60"
    value: float | None = None   # Numeric result
    unit: str = ''               # e.g., "mg/kg", "%"
    standard: str = ''           # e.g., "UNE 83963:2008"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LabResults:
    """Complete lab extraction results for a project."""
    tests: list[LabTestResult] = field(default_factory=list)
    sulfate_mg_kg: float | None = None
    source_file: str = ''
    raw_text: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'sulfate_mg_kg': self.sulfate_mg_kg,
            'source_file': self.source_file,
            'tests': [t.to_dict() for t in self.tests],
        }


def _find_lab_pdf(project_path: Path) -> Path | None:
    """
    Find lab results PDF in the project folder.

    Searches in order:
    1. PDF/ANNEXES/LAB*.pdf
    2. ANNEXES/LAB*.pdf
    3. PDF/ANNEXES/*laboratori*.pdf
    4. Any PDF with 'lab' in name
    """
    search_patterns = [
        'PDF/ANNEXES/LAB*.pdf',
        'PDF/ANNEXES/lab*.pdf',
        'ANNEXES/LAB*.pdf',
        'PDF/ANNEXES/*laboratori*.pdf',
        'PDF/ANNEXES/*LABORATORI*.pdf',
    ]

    for pattern in search_patterns:
        matches = list(project_path.glob(pattern))
        if matches:
            return matches[0]

    return None


def _extract_sulfate(text: str) -> float | None:
    """
    Extract sulfate content in mg/kg from lab report text.

    Common patterns:
    - "Sulfats solubles ... 89.8 mg/kg"
    - "SO4 ... 89,8"
    - "Sulfate content: 89.8 mg/kg"
    - "89.8" near "sulfat" or "SO4" keywords
    """
    for pattern in [
        r'(?i)sulfat[os]?\s+soluble[s]?.*?(\d+[.,]\d+)\s*(?:mg/kg|mg\.kg)',
        r'(?i)sulfat.*?(\d+[.,]\d+)\s*(?:mg/kg|mg\.kg)',
        r'(?i)SO4.*?(\d+[.,]\d+)\s*(?:mg/kg|mg\.kg)',
        r'(?i)sulfat[os]?\s+soluble[s]?.*?(\d+[.,]\d+)',
        r'(?i)(?:resultat|result|valor).*?sulfat.*?(\d+[.,]\d+)',
        r'(?i)(\d+[.,]\d+)\s*(?:mg/kg|mg\.kg).*?sulfat',
    ]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            value_str = match.group(1).replace(',', '.')
            try:
                value = float(value_str)
                if 0 < value < 100000:  # Reasonable range for mg/kg
                    return value
            except ValueError:
                continue

    return None


def _extract_sample_info(text: str) -> dict[str, str]:
    """
    Extract sample identification from lab report text.

    Returns dict with keys: sample_id, location, depth

    Handles TPS lab format where fields are on separate lines:
        Mostra:
        SPT1 S1
        Cota d'extracció (m):
        1,0 - 1,6
    """
    info: dict[str, str] = {}

    # Sample ID: "SPT1 S1" anywhere in text (lab PDFs have jumbled column order)
    # Also try "Mostra:\nSPT-1" or "Mostra: M-1"
    spt_combo = re.search(r'\b(SPT)(\d+)\s+(S)(\d+)\b', text)
    if spt_combo:
        info['sample_id'] = f"{spt_combo.group(1)}-{spt_combo.group(2)}"
        info['location'] = f"{spt_combo.group(3)}-{spt_combo.group(4)}"
    else:
        sample_match = re.search(
            r'(?i)mostra:\s*\n?\s*(SPT-?\d+|M-?\d+|MO?-?\d+)',
            text,
        )
        if sample_match:
            info['sample_id'] = sample_match.group(1).strip()

    # Location fallback: S-1, DPSH-1, etc. (only if not already found)
    if 'location' not in info:
        loc_match = re.search(r'\b(S-\d+|DPSH-\d+|P-\d+)\b', text)
        if loc_match:
            info['location'] = loc_match.group(1)

    # Depth: "Cota d'extracció (m):\n1,0 - 1,6" or inline
    depth_match = re.search(
        r"(?i)cota\s+d['']\s*extracci[oó]\s*\(m\)\s*:\s*\n?\s*"
        r"(\d+[.,]\d+)\s*[-–]\s*(\d+[.,]\d+)",
        text,
    )
    if not depth_match:
        # Fallback: "profunditat" patterns
        depth_match = re.search(
            r'(?i)(?:profunditat|depth|prof)[\s.:]*'
            r'(-?\d+[.,]\d+)\s*(?:a|[-–])\s*(-?\d+[.,]\d+)',
            text,
        )
    if depth_match:
        d1 = depth_match.group(1).replace(',', '.')
        d2 = depth_match.group(2).replace(',', '.')
        info['depth'] = f"-{d1} a -{d2}" if not d1.startswith('-') else f"{d1} a {d2}"

    return info


def _extract_test_type(text: str) -> str:
    """Extract the type of lab test performed."""
    # Look for UNE standard references
    une_match = re.search(r'(UNE\s+\d+[:\-]?\d*)', text)

    if re.search(r'(?i)sulfat', text):
        standard = une_match.group(1) if une_match else 'UNE 83963:2008'
        return f"Contingut en sulfats solubles {standard}"

    if re.search(r'(?i)granulom', text):
        standard = une_match.group(1) if une_match else ''
        return f"Analisi granulometrica {standard}".strip()

    if re.search(r'(?i)atterberg|plasticitat|liquid', text):
        return "Limits d'Atterberg"

    if re.search(r'(?i)humitat|moisture', text):
        return "Contingut d'humitat"

    return "Assaig de laboratori"


def extract_lab_results(project_path: str | Path) -> LabResults:
    """
    Extract laboratory test results from project PDF.

    Args:
        project_path: Path to the project folder

    Returns:
        LabResults with extracted data. Fields may be None if not found.
    """
    project_path = Path(project_path)

    pdf_path = _find_lab_pdf(project_path)
    if not pdf_path:
        logger.info(f"No lab PDF found in {project_path}")
        return LabResults()

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF (fitz) not available, cannot extract lab results")
        return LabResults()

    results = LabResults(source_file=str(pdf_path))

    try:
        doc = fitz.open(str(pdf_path))
        full_text = ''
        for page in doc:
            full_text += page.get_text() + '\n'
        doc.close()
        results.raw_text = full_text
    except Exception as e:
        logger.warning(f"Failed to read lab PDF {pdf_path}: {e}")
        return results

    # Extract sulfate value
    sulfate = _extract_sulfate(full_text)
    if sulfate is not None:
        results.sulfate_mg_kg = sulfate
        logger.info(f"Extracted sulfate: {sulfate} mg/kg from {pdf_path.name}")

    # Extract sample info
    sample_info = _extract_sample_info(full_text)

    # Extract test type
    test_type = _extract_test_type(full_text)

    # Build test result
    if sulfate is not None or sample_info:
        test = LabTestResult(
            type=test_type,
            sample_id=sample_info.get('sample_id', ''),
            location=sample_info.get('location', ''),
            depth=sample_info.get('depth', ''),
            value=sulfate,
            unit='mg/kg' if sulfate else '',
        )
        results.tests.append(test)

    return results
