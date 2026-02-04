#!/usr/bin/env python3
"""
G3DT Field Data Extractor

Orchestrates extraction of data from field document PDFs using Claude vision.
Produces validation JSON files for human review.

Usage:
    from validation.extractor import extract_dpsh_from_pdf, compare_with_excel

    # Extract from PDF (requires Claude API)
    result = extract_dpsh_from_pdf(pdf_path, project_path)

    # Compare extracted data with Excel
    comparison = compare_with_excel(validation_file, excel_data)

Author: Eficients.cat
Date: 2026-02-04
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Handle both module and direct execution imports
if __name__ == '__main__':
    # Direct execution - add parent to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from automation.validation.schemas import (
        ValidationStatus,
        ExtractionMethod,
        DPSHReadingExtracted,
        DPSHTestExtracted,
        DPSHValidationFile,
        SondeigLayerExtracted,
        SondeigTestExtracted,
        SondeigValidationFile,
    )
else:
    # Module import
    from .schemas import (
        ValidationStatus,
        ExtractionMethod,
        DPSHReadingExtracted,
        DPSHTestExtracted,
        DPSHValidationFile,
        SondeigLayerExtracted,
        SondeigTestExtracted,
        SondeigValidationFile,
    )


def create_validation_folder(project_path: Path) -> Path:
    """
    Create validation folder in project directory if it doesn't exist.

    Args:
        project_path: Path to the project folder

    Returns:
        Path to the validation folder
    """
    validation_folder = project_path / "validation"
    validation_folder.mkdir(exist_ok=True)
    return validation_folder


def parse_dpsh_extraction_response(
    response_json: dict,
    source_file: str = "PENETROS.pdf"
) -> DPSHValidationFile:
    """
    Parse Claude's extraction response into a DPSHValidationFile.

    Args:
        response_json: JSON dict from Claude vision extraction
        source_file: Name of the source PDF file

    Returns:
        DPSHValidationFile ready for review
    """
    dpsh_tests = []

    for test_data in response_json.get('dpsh_tests', []):
        readings = []
        for r in test_data.get('readings', []):
            readings.append(DPSHReadingExtracted(
                depth_m=r.get('depth_m', 0.0),
                n20=r.get('n20', '??'),
                confidence=r.get('confidence', 1.0),
                note=r.get('note'),
                torque=r.get('torque'),
                water_indicator=r.get('water_indicator', False),
            ))

        dpsh_tests.append(DPSHTestExtracted(
            test_id=test_data.get('test_id', 'P-?'),
            readings=readings,
            refusal_depth_m=test_data.get('refusal_depth_m'),
            refusal_detected=test_data.get('refusal_detected', False),
            water_detected=test_data.get('water_detected', False),
            water_depth_m=test_data.get('water_depth_m'),
            correction_factor=test_data.get('correction_factor', 0.83),
            extraction_notes=test_data.get('extraction_notes'),
        ))

    return DPSHValidationFile(
        source_file=source_file,
        extraction_method=ExtractionMethod.CLAUDE_VISION,
        overall_confidence=response_json.get('overall_confidence', 1.0),
        status=ValidationStatus.PENDING,
        dpsh_tests=dpsh_tests,
    )


def parse_sondeig_extraction_response(
    response_json: dict,
    source_file: str = "SONDEIG.pdf"
) -> SondeigValidationFile:
    """
    Parse Claude's extraction response into a SondeigValidationFile.

    Args:
        response_json: JSON dict from Claude vision extraction
        source_file: Name of the source PDF file

    Returns:
        SondeigValidationFile ready for review
    """
    sondeig_tests = []

    for test_data in response_json.get('sondeig_tests', []):
        layers = []
        for layer in test_data.get('layers', []):
            layers.append(SondeigLayerExtracted(
                depth_from_m=layer.get('depth_from_m', 0.0),
                depth_to_m=layer.get('depth_to_m'),
                description=layer.get('description', ''),
                uscs_classification=layer.get('uscs_classification'),
                color=layer.get('color'),
                moisture=layer.get('moisture'),
                consistency=layer.get('consistency'),
                density=layer.get('density'),
                confidence=layer.get('confidence', 1.0),
                note=layer.get('note'),
            ))

        sondeig_tests.append(SondeigTestExtracted(
            test_id=test_data.get('test_id', 'S-?'),
            total_depth_m=test_data.get('total_depth_m', 0.0),
            layers=layers,
            water_level_m=test_data.get('water_level_m'),
            rock_detected=test_data.get('rock_detected', False),
            rock_depth_m=test_data.get('rock_depth_m'),
            extraction_notes=test_data.get('extraction_notes'),
        ))

    return SondeigValidationFile(
        source_file=source_file,
        extraction_method=ExtractionMethod.CLAUDE_VISION,
        overall_confidence=response_json.get('overall_confidence', 1.0),
        status=ValidationStatus.PENDING,
        sondeig_tests=sondeig_tests,
    )


def save_extraction_result(
    validation_file: DPSHValidationFile | SondeigValidationFile,
    project_path: Path,
    filename: str = "dpsh_extracted.json"
) -> Path:
    """
    Save extraction result to the validation folder.

    Args:
        validation_file: The validation file to save
        project_path: Path to the project folder
        filename: Output filename (default: dpsh_extracted.json)

    Returns:
        Path to the saved file
    """
    validation_folder = create_validation_folder(project_path)
    output_path = validation_folder / filename
    validation_file.save(output_path)
    return output_path


def compare_with_excel(
    validation_file: DPSHValidationFile,
    excel_data: dict,
) -> dict[str, Any]:
    """
    Compare extracted PDF data with Excel data for verification.

    This helps identify discrepancies between the handwritten field sheet
    and the digitized Excel file.

    Args:
        validation_file: Extracted data from PDF
        excel_data: DPSH data from Excel (from DPSHData.to_dict())

    Returns:
        Comparison report with matches and discrepancies
    """
    comparison = {
        'timestamp': datetime.now().isoformat(),
        'matches': [],
        'discrepancies': [],
        'pdf_only': [],
        'excel_only': [],
        'summary': {},
    }

    # Build lookup for Excel tests
    excel_tests = {t['test_id']: t for t in excel_data.get('tests', [])}
    pdf_test_ids = {t.test_id for t in validation_file.dpsh_tests}
    excel_test_ids = set(excel_tests.keys())

    # Find tests only in one source
    comparison['pdf_only'] = list(pdf_test_ids - excel_test_ids)
    comparison['excel_only'] = list(excel_test_ids - pdf_test_ids)

    # Compare common tests
    common_tests = pdf_test_ids & excel_test_ids
    total_values = 0
    matching_values = 0

    for test_id in common_tests:
        pdf_test = next(t for t in validation_file.dpsh_tests if t.test_id == test_id)
        excel_test = excel_tests[test_id]
        excel_readings = {r['depth_m']: r['n20'] for r in excel_test.get('readings', [])}

        for pdf_reading in pdf_test.readings:
            total_values += 1
            depth = pdf_reading.depth_m
            pdf_n20 = pdf_reading.n20

            if depth in excel_readings:
                excel_n20 = excel_readings[depth]

                if pdf_n20 == '??' or pdf_reading.confidence < 0.5:
                    # PDF value uncertain, flag for review
                    comparison['discrepancies'].append({
                        'test_id': test_id,
                        'depth_m': depth,
                        'pdf_value': pdf_n20,
                        'excel_value': excel_n20,
                        'pdf_confidence': pdf_reading.confidence,
                        'type': 'pdf_uncertain',
                    })
                elif pdf_n20 == excel_n20:
                    matching_values += 1
                    comparison['matches'].append({
                        'test_id': test_id,
                        'depth_m': depth,
                        'value': pdf_n20,
                    })
                else:
                    comparison['discrepancies'].append({
                        'test_id': test_id,
                        'depth_m': depth,
                        'pdf_value': pdf_n20,
                        'excel_value': excel_n20,
                        'pdf_confidence': pdf_reading.confidence,
                        'type': 'value_mismatch',
                    })
            else:
                comparison['discrepancies'].append({
                    'test_id': test_id,
                    'depth_m': depth,
                    'pdf_value': pdf_n20,
                    'excel_value': None,
                    'type': 'depth_not_in_excel',
                })

    # Summary
    comparison['summary'] = {
        'total_tests_pdf': len(validation_file.dpsh_tests),
        'total_tests_excel': len(excel_tests),
        'common_tests': len(common_tests),
        'total_values_compared': total_values,
        'matching_values': matching_values,
        'match_rate': round(matching_values / total_values * 100, 1) if total_values > 0 else 0,
        'discrepancies_count': len(comparison['discrepancies']),
    }

    return comparison


def create_from_excel(
    excel_data: dict,
    source_file: str = "DPSH.xls"
) -> DPSHValidationFile:
    """
    Create a validation file from existing Excel data.

    Useful when PDFs are not available or as a fallback.
    All values get confidence 1.0 since they're from digitized source.

    Args:
        excel_data: DPSH data from DPSHData.to_dict()
        source_file: Source filename for reference

    Returns:
        DPSHValidationFile with Excel data
    """
    dpsh_tests = []

    for test_dict in excel_data.get('tests', []):
        readings = []
        for r in test_dict.get('readings', []):
            readings.append(DPSHReadingExtracted(
                depth_m=r['depth_m'],
                n20=r['n20'],
                confidence=1.0,  # Excel data is already digitized
                note=None,
                torque=r.get('torque'),
                water_indicator=r.get('water_level', False),
            ))

        # Determine refusal
        refusal_detected = test_dict.get('refusal_reached', False)
        refusal_depth = test_dict.get('refusal_depth_m')

        dpsh_tests.append(DPSHTestExtracted(
            test_id=test_dict['test_id'],
            readings=readings,
            refusal_depth_m=refusal_depth,
            refusal_detected=refusal_detected,
            water_detected=test_dict.get('water_detected', False),
            water_depth_m=test_dict.get('water_depth_m'),
            correction_factor=test_dict.get('correction_factor', 0.83),
        ))

    return DPSHValidationFile(
        source_file=source_file,
        extraction_method=ExtractionMethod.EXCEL_IMPORT,
        overall_confidence=1.0,
        status=ValidationStatus.APPROVED,  # Excel data is considered verified
        dpsh_tests=dpsh_tests,
    )


def load_validation_file(
    project_path: Path,
    filename: str = "dpsh_approved.json"
) -> DPSHValidationFile | None:
    """
    Load a validation file from the project's validation folder.

    Args:
        project_path: Path to the project folder
        filename: Validation filename to load

    Returns:
        DPSHValidationFile if found and valid, None otherwise
    """
    validation_path = project_path / "validation" / filename
    if not validation_path.exists():
        return None

    try:
        return DPSHValidationFile.load(validation_path)
    except Exception as e:
        print(f"Warning: Could not load validation file {validation_path}: {e}")
        return None


# ============================================================================
# PDF Extraction and Comparison Functions
# ============================================================================

def simulate_pdf_extraction(
    excel_data: dict,
    source_file: str = "PENETROS.pdf"
) -> DPSHValidationFile:
    """
    Generate simulated PDF extraction based on Excel data.

    This creates realistic extracted data with intentional variations to simulate:
    - OCR uncertainty (low confidence values)
    - Illegible handwriting (marked as '??')
    - Minor misreads (values off by a few counts)

    This is a temporary function for testing the workflow until real PDF
    reading is implemented.

    Args:
        excel_data: DPSH data from DPSHData.to_dict()
        source_file: Name to use for source_file field

    Returns:
        DPSHValidationFile with simulated extraction
    """
    import random
    random.seed(42)  # Reproducible for testing

    dpsh_tests = []

    for test_dict in excel_data.get('tests', []):
        readings = []
        for i, r in enumerate(test_dict.get('readings', [])):
            excel_n20 = r['n20']
            confidence = 1.0
            note = None
            pdf_n20: int | str = excel_n20

            # Simulate various extraction issues (~15% of values)
            roll = random.random()
            if roll < 0.05:
                # 5%: Completely illegible
                pdf_n20 = '??'
                confidence = 0.0
                note = "illegible - ink smudged"
            elif roll < 0.10:
                # 5%: Minor misread (off by 1-3)
                offset = random.choice([-2, -1, 1, 2])
                pdf_n20 = max(1, excel_n20 + offset)
                confidence = 0.75
                note = f"PDF shows {pdf_n20}, may be {excel_n20}"
            elif roll < 0.15:
                # 5%: Low confidence but correct
                confidence = 0.85
                note = "faint handwriting"

            # Mark refusal readings
            if excel_n20 >= 100 and note is None:
                note = "refusal marker (R)"

            readings.append(DPSHReadingExtracted(
                depth_m=r['depth_m'],
                n20=pdf_n20,
                confidence=confidence,
                note=note,
                torque=r.get('torque'),
                water_indicator=r.get('water_level', False),
            ))

        # Determine refusal from Excel data
        refusal_detected = test_dict.get('refusal_reached', False)
        refusal_depth = test_dict.get('refusal_depth_m')

        dpsh_tests.append(DPSHTestExtracted(
            test_id=test_dict['test_id'],
            readings=readings,
            refusal_depth_m=refusal_depth,
            refusal_detected=refusal_detected,
            water_detected=test_dict.get('water_detected', False),
            water_depth_m=test_dict.get('water_depth_m'),
            correction_factor=test_dict.get('correction_factor', 0.83),
            extraction_notes="Simulated extraction for testing",
        ))

    # Calculate overall confidence
    all_confidences = [
        r.confidence
        for t in dpsh_tests
        for r in t.readings
    ]
    overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 1.0

    return DPSHValidationFile(
        source_file=source_file,
        extraction_method=ExtractionMethod.CLAUDE_VISION,
        overall_confidence=round(overall_confidence, 2),
        status=ValidationStatus.PENDING,
        dpsh_tests=dpsh_tests,
    )


def compare_readings(
    pdf_test: DPSHTestExtracted,
    excel_test: dict,
) -> list[DPSHReadingExtracted]:
    """
    Compare PDF extraction with Excel data, flag discrepancies.

    For each reading:
    - Add excel_value field
    - Set has_discrepancy = True if pdf.n20 != excel.n20
    - Keep confidence and notes from PDF extraction

    Args:
        pdf_test: Extracted test from PDF
        excel_test: Test data from Excel (dict format)

    Returns:
        List of readings with excel_value and has_discrepancy populated
    """
    # Build lookup for Excel readings by depth
    excel_readings = {r['depth_m']: r['n20'] for r in excel_test.get('readings', [])}

    compared_readings = []
    for pdf_reading in pdf_test.readings:
        depth = pdf_reading.depth_m
        excel_n20 = excel_readings.get(depth)

        # Determine if there's a discrepancy
        has_discrepancy = False
        if pdf_reading.n20 == '??' or pdf_reading.confidence < 0.5:
            # Uncertain PDF value counts as discrepancy
            has_discrepancy = True
        elif excel_n20 is not None and pdf_reading.n20 != excel_n20:
            # Value mismatch
            has_discrepancy = True

        # Create new reading with comparison fields
        compared_readings.append(DPSHReadingExtracted(
            depth_m=pdf_reading.depth_m,
            n20=pdf_reading.n20,
            confidence=pdf_reading.confidence,
            note=pdf_reading.note,
            torque=pdf_reading.torque,
            water_indicator=pdf_reading.water_indicator,
            excel_value=excel_n20,
            has_discrepancy=has_discrepancy,
        ))

    return compared_readings


def extract_and_compare(
    pdf_path: Path,
    excel_path: Path,
    output_dir: Path | None = None,
) -> DPSHValidationFile:
    """
    Extract DPSH data from PDF, compare with Excel, and save validation file.

    Currently uses simulated extraction. Will be updated to use real PDF
    reading when Claude vision integration is complete.

    Args:
        pdf_path: Path to PENETROS.pdf
        excel_path: Path to DPSH Excel file
        output_dir: Where to save validation JSON (default: pdf_path.parent / "validation")

    Returns:
        DPSHValidationFile with discrepancies flagged
    """
    # Import DPSHExtractor
    if __name__ == '__main__':
        from automation.dpsh_extractor import DPSHExtractor
    else:
        from ..dpsh_extractor import DPSHExtractor

    # Validate inputs
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    # Extract Excel data
    extractor = DPSHExtractor(str(excel_path))
    excel_data = extractor.extract_all().to_dict()

    # Simulate PDF extraction (temporary)
    validation_file = simulate_pdf_extraction(
        excel_data,
        source_file=pdf_path.name
    )

    # Build Excel lookup by test_id
    excel_tests = {t['test_id']: t for t in excel_data.get('tests', [])}

    # Compare each test
    compared_tests = []
    total_values = 0
    discrepancy_count = 0

    for pdf_test in validation_file.dpsh_tests:
        excel_test = excel_tests.get(pdf_test.test_id)
        if excel_test:
            compared_readings = compare_readings(pdf_test, excel_test)
            total_values += len(compared_readings)
            discrepancy_count += sum(1 for r in compared_readings if r.has_discrepancy)

            compared_tests.append(DPSHTestExtracted(
                test_id=pdf_test.test_id,
                readings=compared_readings,
                refusal_depth_m=pdf_test.refusal_depth_m,
                refusal_detected=pdf_test.refusal_detected,
                water_detected=pdf_test.water_detected,
                water_depth_m=pdf_test.water_depth_m,
                correction_factor=pdf_test.correction_factor,
                extraction_notes=pdf_test.extraction_notes,
            ))
        else:
            # Test not in Excel - keep as is
            compared_tests.append(pdf_test)
            total_values += len(pdf_test.readings)

    # Update validation file with compared tests
    validation_file.dpsh_tests = compared_tests
    validation_file.excel_comparison = {
        'has_excel': True,
        'excel_file': excel_path.name,
        'total_values': total_values,
        'matches': total_values - discrepancy_count,
        'discrepancies': discrepancy_count,
    }

    # Save to output directory
    if output_dir is None:
        output_dir = pdf_path.parent / "validation"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "dpsh_extracted.json"
    validation_file.save(output_path)

    return validation_file


def main():
    """CLI interface for extract_and_compare."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract DPSH data from PDF and compare with Excel",
        prog="python -m automation.validation.extractor"
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to PENETROS.pdf"
    )
    parser.add_argument(
        "excel_path",
        type=Path,
        help="Path to DPSH Excel file (.xls)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory for validation JSON (default: pdf_path.parent/validation)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full JSON instead of summary"
    )

    args = parser.parse_args()

    try:
        result = extract_and_compare(
            pdf_path=args.pdf_path,
            excel_path=args.excel_path,
            output_dir=args.output
        )

        if args.json:
            print(result.to_json())
        else:
            # Summary output
            comparison = result.excel_comparison
            print(f"\n{'='*60}")
            print(f"DPSH Extraction Complete: {result.source_file}")
            print(f"{'='*60}")
            print(f"Status: {result.status.value}")
            print(f"Method: {result.extraction_method.value}")
            print(f"Overall confidence: {result.overall_confidence:.0%}")
            print(f"\nComparison with Excel ({comparison.get('excel_file', 'N/A')}):")
            print(f"  Total values: {comparison.get('total_values', 0)}")
            print(f"  Matches: {comparison.get('matches', 0)}")
            print(f"  Discrepancies: {comparison.get('discrepancies', 0)}")

            # Show discrepancies
            print(f"\nDiscrepancies found:")
            for test in result.dpsh_tests:
                for r in test.readings:
                    if r.has_discrepancy:
                        excel_val = r.excel_value if r.excel_value is not None else "N/A"
                        print(f"  {test.test_id} @ {r.depth_m}m: PDF={r.n20}, Excel={excel_val}")
                        if r.note:
                            print(f"    Note: {r.note}")

            # Output path
            output_dir = args.output or args.pdf_path.parent / "validation"
            print(f"\nValidation file saved to: {output_dir / 'dpsh_extracted.json'}")
            print(f"\nNext: Open templates/validation/review.html to review discrepancies")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
