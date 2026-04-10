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
    # Lab metadata fields for prefills
    lab_field_company: str = ''
    lab_testing_company: str = ''
    lab_field_description: str = ''
    lab_testing_description: str = ''
    lab_location: str = ''
    lab_sample_id: str = ''
    lab_depth: str = ''
    lab_tests_text: str = ''
    language: str = 'ca'
    gtl_source_file: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'sulfate_mg_kg': self.sulfate_mg_kg,
            'source_file': self.source_file,
            'tests': [t.to_dict() for t in self.tests],
            'lab_field_company': self.lab_field_company,
            'lab_testing_company': self.lab_testing_company,
            'lab_field_description': self.lab_field_description,
            'lab_testing_description': self.lab_testing_description,
            'lab_location': self.lab_location,
            'lab_sample_id': self.lab_sample_id,
            'lab_depth': self.lab_depth,
            'lab_tests_text': self.lab_tests_text,
            'language': self.language,
            'gtl_source_file': self.gtl_source_file,
        }


def _find_lab_pdf(project_path: Path) -> Path | None:
    """
    Find lab results PDF in the project folder.

    Searches in order:
    0. file_mapping.json → lab_results_pdf role
    1. PDF/ANNEXES/LAB*.pdf
    2. ANNEXES/LAB*.pdf
    3. PDF/ANNEXES/*laboratori*.pdf
    4. Any PDF with 'lab' in name
    """
    # Check file_mapping.json first (single source of truth)
    mapping_path = project_path / 'file_mapping.json'
    if mapping_path.exists():
        try:
            data = json.loads(mapping_path.read_text(encoding='utf-8'))
            lab_role = data.get('roles', {}).get('lab_results_pdf')
            if lab_role:
                candidate = project_path / lab_role['path']
                if candidate.exists():
                    return candidate
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Fallback to glob patterns
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
                if 0 <= value < 100000:  # Reasonable range for mg/kg
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

    # Sample ID: "SPT1 S1" or "SPT1 P3" anywhere in text (lab PDFs have jumbled column order)
    # S = sondeig location, P = penetrometer location
    spt_combo = re.search(r'\b(SPT)(\d+)\s+([SP])(\d+)\b', text)
    if spt_combo:
        info['sample_id'] = f"{spt_combo.group(1)}-{spt_combo.group(2)}"
        info['location'] = f"{spt_combo.group(3)}-{spt_combo.group(4)}"
    else:
        sample_match = re.search(
            r'(?i)(?:mostra|muestra):\s*\n?\s*(SPT-?\d+|M-?\d+|MO?-?\d+|MA-?\d+)',
            text,
        )
        if sample_match:
            info['sample_id'] = sample_match.group(1).strip()
        # Fallback for non-SPT samples: "Tipus de mostra: Alterada" → sample type
        if 'sample_id' not in info:
            type_match = re.search(
                r'(?i)Tipus\s+de\s+mostra\s*:\s*\n?\s*(SPT|Alterada|Inalt[e·]rada|Inalterada)',
                text,
            )
            if type_match:
                info['sample_type'] = type_match.group(1).strip()

    # Location fallback: S-1, DPSH-1, P-1, etc. (only if not already found)
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


def _normalize_une(raw: str) -> str:
    """Normalize UNE standard refs like 'UNE 83963 / 08' → 'UNE 83963:2008'."""
    m = re.match(r'(UNE)\s+(\d+)\s*[:/]\s*(\d+)', raw.strip())
    if m:
        year = m.group(3)
        if len(year) == 2:
            year = ('19' if int(year) > 50 else '20') + year
        return f"{m.group(1)} {m.group(2)}:{year}"
    # No year part — just normalize whitespace
    return re.sub(r'\s+', ' ', raw).strip()


def _extract_test_type(text: str) -> str:
    """Extract the type of lab test performed."""

    if re.search(r'(?i)sulfat', text):
        # Look for UNE near "sulfat" keyword to avoid picking up sample-prep standards
        une_sulfat = re.search(r'(?i)sulfat.*?(UNE\s+\d+(?:\s*[:/]\s*\d+)?)', text)
        standard = _normalize_une(une_sulfat.group(1)) if une_sulfat else 'UNE 83963:2008'
        return f"Contingut en sulfats solubles {standard}"

    if re.search(r'(?i)granulom', text):
        une_gran = re.search(r'(?i)granulom.*?(UNE\s+\d+(?:\s*[:/]\s*\d+)?)', text)
        standard = _normalize_une(une_gran.group(1)) if une_gran else ''
        return f"Analisi granulometrica {standard}".strip()

    if re.search(r'(?i)atterberg|plasticitat|liquid', text):
        return "Limits d'Atterberg"

    if re.search(r'(?i)humitat|moisture', text):
        return "Contingut d'humitat"

    return "Assaig de laboratori"


def _find_gtl_pdf(project_path: Path) -> Path | None:
    """Find GTL lab report PDF via file_mapping.json gtl_report role."""
    mapping_path = project_path / 'file_mapping.json'
    if mapping_path.exists():
        try:
            data = json.loads(mapping_path.read_text(encoding='utf-8'))
            gtl_role = data.get('roles', {}).get('gtl_report')
            if gtl_role:
                candidate = project_path / gtl_role['path']
                if candidate.exists():
                    return candidate
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return None


def _extract_tests_text(text: str, language: str = 'ca') -> str:
    """Extract the tests performed text from GTL page 2."""
    patterns = [
        r'(?i)ASSAIGS\s+REALITZATS\s*:\s*(.+?)(?:\n\s*\n|OBSERVACIONS|RESULTATS|Pàgina|$)',
        r'(?i)ENSAYOS\s+REALIZADOS\s*:\s*(.+?)(?:\n\s*\n|OBSERVACIONES|RESULTADOS|Página|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            result = match.group(1).strip()
            return result[:500] if len(result) > 500 else result
    return ''


def _detect_language(text: str) -> str:
    """Detect CA vs ES from GTL PDF text."""
    es_markers = ['Muestra', 'Profundidad', 'Ensayos', 'Punto']
    ca_markers = ['Mostra', 'Profunditat', 'Assaigs', 'Punt']
    es_count = sum(1 for m in es_markers if m.lower() in text.lower())
    ca_count = sum(1 for m in ca_markers if m.lower() in text.lower())
    return 'es' if es_count > ca_count else 'ca'


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

    # Try GTL report for full sample metadata
    gtl_path = _find_gtl_pdf(project_path)
    gtl_text = ''
    if gtl_path:
        results.gtl_source_file = str(gtl_path)
        try:
            doc = fitz.open(str(gtl_path))
            for page in doc:
                gtl_text += page.get_text() + '\n'
            doc.close()
        except Exception as e:
            logger.warning(f"Failed to read GTL PDF {gtl_path}: {e}")

    # Use GTL text if available, otherwise fall back to lab PDF text
    metadata_text = gtl_text or full_text

    # Detect language
    lang = _detect_language(metadata_text)
    results.language = lang

    # Extract sample info from GTL (or lab PDF as fallback)
    if metadata_text:
        gtl_sample_info = _extract_sample_info(metadata_text) if gtl_text else sample_info

        if gtl_sample_info.get('location'):
            results.lab_location = gtl_sample_info['location']

        if gtl_sample_info.get('sample_id'):
            results.lab_sample_id = gtl_sample_info['sample_id']

        if gtl_sample_info.get('depth'):
            results.lab_depth = f"{gtl_sample_info['depth']} m"

        results.lab_tests_text = _extract_tests_text(metadata_text, lang)

    # Set constant/template fields
    results.lab_field_company = 'TPS PROSPECCIÓ DEL SUBSÒL SL'
    results.lab_testing_company = 'TPS PROSPECCIÓ DEL SUBSÒL SL'

    if lang == 'es':
        results.lab_field_description = "laboratorio de ensayos para el control de calidad de la edificación"
        results.lab_testing_description = "laboratorio de ensayos para el control de calidad de la edificación"
    else:
        results.lab_field_description = "laboratori d'assaigs per al control de qualitat de l'edificació"
        results.lab_testing_description = "laboratori d'assaigs per al control de qualitat de l'edificació"

    return results
