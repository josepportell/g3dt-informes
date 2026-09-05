#!/usr/bin/env python3
"""
G3DT DPSH Data Extractor

Extracts penetration test data from DPSH Excel files (.xls format).
This is the foundation module for report automation - most calculated
values in the geotechnical report derive from this data.

Usage:
    uv run --with xlrd dpsh_extractor.py <path_to_dpsh.xls>

    Or as a module:
    from dpsh_extractor import DPSHExtractor
    extractor = DPSHExtractor('path/to/DPSH.xls')
    data = extractor.extract_all()

Author: Eficients.cat
Date: 2026-02-02
"""

import json
import sys
from dataclasses import dataclass, field, asdict
import re
from pathlib import Path
from typing import Optional


@dataclass
class DPSHReading:
    """Single depth reading from a DPSH test."""
    depth_m: float          # Depth in meters (negative = below surface)
    n20: int                # Raw blow count per 20cm
    nb: float               # Normalized blow count (N20 / correction_factor)
    torque: Optional[float] = None  # PAR measurement (rarely used)
    water_level: bool = False       # Was water detected at this depth?
    soil_level: Optional[str] = None  # Soil level designation if marked


@dataclass
class DPSHTest:
    """Complete data for one DPSH penetration test point."""
    test_id: str                    # e.g., "P-1", "P-2"
    readings: list[DPSHReading] = field(default_factory=list)
    correction_factor: float = 0.83  # Energy correction (default)
    refusal_depth_annotated: Optional[float] = None  # "R:" annotation from handwritten field sheet

    @property
    def max_depth(self) -> float:
        """Maximum penetration depth (most negative value)."""
        if not self.readings:
            return 0.0
        return min(r.depth_m for r in self.readings)

    @property
    def depth_reached(self) -> float:
        """Absolute depth reached (positive value for display).

        Prefers the handwritten "R:" refusal annotation (from dpsh_extracted.json)
        over the Excel last-row depth, since the Excel rounds up to the next
        0.20m grid interval while the field annotation is the actual depth.
        """
        if self.refusal_depth_annotated is not None:
            return abs(self.refusal_depth_annotated)
        return abs(self.max_depth)

    @property
    def n20_values(self) -> list[int]:
        """List of all N20 blow counts."""
        return [r.n20 for r in self.readings]

    @property
    def average_n20(self) -> float:
        """Average N20 across all readings."""
        values = self.n20_values
        if not values:
            return 0.0
        return sum(values) / len(values)

    @property
    def refusal_reached(self) -> bool:
        """Whether test ended in refusal (N20 >= 100)."""
        return any(r.n20 >= 100 for r in self.readings)

    @property
    def refusal_depth(self) -> Optional[float]:
        """Depth at which refusal occurred, if any."""
        for r in self.readings:
            if r.n20 >= 100:
                return r.depth_m
        return None

    @property
    def water_detected(self) -> bool:
        """Whether water level was encountered."""
        return any(r.water_level for r in self.readings)

    @property
    def water_depth(self) -> Optional[float]:
        """Depth at which water was first detected."""
        for r in self.readings:
            if r.water_level:
                return r.depth_m
        return None

    def average_n20_for_range(self, min_depth: float, max_depth: float) -> float:
        """
        Calculate average N20 for a specific depth range.
        Useful for calculating parameters per soil level.

        Args:
            min_depth: Shallower depth (e.g., -0.5)
            max_depth: Deeper depth (e.g., -2.0)
        """
        values = [r.n20 for r in self.readings
                  if min_depth >= r.depth_m >= max_depth]
        if not values:
            return 0.0
        return sum(values) / len(values)


@dataclass
class DPSHData:
    """Complete DPSH data for a project."""
    expedient: str
    tests: list[DPSHTest] = field(default_factory=list)
    source_file: str = ""

    @property
    def num_tests(self) -> int:
        """Number of DPSH tests performed."""
        return len(self.tests)

    @property
    def test_ids(self) -> list[str]:
        """List of all test IDs."""
        return [t.test_id for t in self.tests]

    @property
    def overall_average_n20(self) -> float:
        """Weighted average N20 across all tests.

        Excludes refusal values (N20 >= 100) and weights shallow readings
        (first 1.0m depth, ~5 readings per test) at 2x to approximate
        Eva's focus on foundation soil zone.
        """
        weighted_sum = 0.0
        total_weight = 0.0

        for test in self.tests:
            for i, reading in enumerate(test.readings):
                if reading.n20 >= 100:
                    continue
                weight = 2.0 if i < 5 else 1.0
                weighted_sum += reading.n20 * weight
                total_weight += weight

        if total_weight == 0:
            all_non_refusal = []
            for test in self.tests:
                all_non_refusal.extend(v for v in test.n20_values if v < 100)
            if not all_non_refusal:
                return 0.0
            return sum(all_non_refusal) / len(all_non_refusal)

        return weighted_sum / total_weight

    @property
    def raw_average_n20(self) -> float:
        """Simple arithmetic mean of ALL N20 readings (including refusal)."""
        all_values = []
        for test in self.tests:
            all_values.extend(test.n20_values)
        if not all_values:
            return 0.0
        return sum(all_values) / len(all_values)

    @property
    def any_water_detected(self) -> bool:
        """Whether water was detected in any test."""
        return any(t.water_detected for t in self.tests)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'expedient': self.expedient,
            'source_file': self.source_file,
            'num_tests': self.num_tests,
            'test_ids': self.test_ids,
            'overall_average_n20': round(self.overall_average_n20, 2),
            'any_water_detected': self.any_water_detected,
            'tests': [
                {
                    'test_id': t.test_id,
                    'correction_factor': t.correction_factor,
                    'depth_reached_m': round(t.depth_reached, 2),
                    'average_n20': round(t.average_n20, 2),
                    'refusal_reached': t.refusal_reached,
                    'refusal_depth_m': round(abs(t.refusal_depth), 2) if t.refusal_depth else None,
                    'water_detected': t.water_detected,
                    'water_depth_m': round(abs(t.water_depth), 2) if t.water_depth else None,
                    'readings': [
                        {
                            'depth_m': round(abs(r.depth_m), 2),
                            'n20': r.n20,
                            'nb': round(r.nb, 2),
                            'torque': r.torque,
                            'water_level': r.water_level,
                            'soil_level': r.soil_level,
                        }
                        for r in t.readings
                    ]
                }
                for t in self.tests
            ]
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class DPSHExtractor:
    """
    Extracts DPSH penetration test data from Excel files.

    The DPSH Excel format (as used by G3DT):
    - One sheet per test point (P-1, P-2, etc.)
    - Row 14, Column D: Correction factor (typically 0.83)
    - Row 15: Headers
    - Row 16+: Data rows
    - Column B: Depth (negative values, meters)
    - Column C: N20 (blow count per 20cm)
    - Column D: NB (normalized = N20 / correction_factor)
    - Column E: Torque (PAR) - rarely used
    - Column F: Water level indicator (N.F.)
    - Column G: Soil level designation
    """

    # Excel structure constants
    CORRECTION_FACTOR_ROW = 13  # 0-indexed (row 14 in Excel)
    CORRECTION_FACTOR_COL = 3   # Column D
    HEADER_ROW = 14             # 0-indexed (row 15 in Excel)
    DATA_START_ROW = 15        # 0-indexed (row 16 in Excel)

    # Column indices (0-indexed)
    COL_DEPTH = 1      # Column B
    COL_N20 = 2        # Column C
    COL_NB = 3         # Column D
    COL_TORQUE = 4     # Column E
    COL_WATER = 5      # Column F
    COL_LEVEL = 6      # Column G

    def __init__(self, filepath: str):
        """
        Initialize extractor with path to DPSH Excel file.

        Args:
            filepath: Path to the .xls file
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"DPSH file not found: {filepath}")

        # Extract expedient from filename (e.g., "4001612_DPSH.xls" -> "4001612")
        self.expedient = self.filepath.stem.split('_')[0]

        self._workbook = None

    def _open_workbook(self):
        """Open the Excel workbook using xlrd."""
        try:
            import xlrd
        except ImportError:
            raise ImportError(
                "xlrd is required. Install with: pip install xlrd\n"
                "Or run with: uv run --with xlrd dpsh_extractor.py"
            )

        self._workbook = xlrd.open_workbook(str(self.filepath))
        return self._workbook

    def _extract_correction_factor(self, sheet) -> float:
        """Extract the correction factor from cell D14."""
        try:
            value = sheet.cell_value(self.CORRECTION_FACTOR_ROW, self.CORRECTION_FACTOR_COL)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        except (IndexError, ValueError):
            pass
        return 0.83  # Default correction factor

    def _extract_test(self, sheet) -> DPSHTest:
        """Extract data from a single test sheet."""
        test_id = sheet.name
        correction_factor = self._extract_correction_factor(sheet)

        readings = []
        for row_idx in range(self.DATA_START_ROW, sheet.nrows):
            try:
                depth = sheet.cell_value(row_idx, self.COL_DEPTH)
                n20_raw = sheet.cell_value(row_idx, self.COL_N20)

                # Skip rows without valid data
                if not isinstance(depth, (int, float)):
                    continue
                if not isinstance(n20_raw, (int, float)) or n20_raw <= 0:
                    continue

                n20 = int(n20_raw)
                nb = n20 / correction_factor

                # Optional fields
                torque = None
                torque_raw = sheet.cell_value(row_idx, self.COL_TORQUE)
                if isinstance(torque_raw, (int, float)) and torque_raw > 0:
                    torque = float(torque_raw)

                water_level = False
                water_raw = sheet.cell_value(row_idx, self.COL_WATER)
                if water_raw and str(water_raw).strip():
                    water_level = True

                soil_level = None
                level_raw = sheet.cell_value(row_idx, self.COL_LEVEL)
                if level_raw and str(level_raw).strip():
                    soil_level = str(level_raw).strip()

                reading = DPSHReading(
                    depth_m=float(depth),
                    n20=n20,
                    nb=nb,
                    torque=torque,
                    water_level=water_level,
                    soil_level=soil_level
                )
                readings.append(reading)

            except (IndexError, ValueError) as e:
                # Skip problematic rows
                continue

        return DPSHTest(
            test_id=test_id,
            readings=readings,
            correction_factor=correction_factor
        )

    def extract_all(self) -> DPSHData:
        """
        Extract all DPSH data from the Excel file.

        Returns:
            DPSHData object with all tests and readings
        """
        wb = self._open_workbook()

        tests = []
        for sheet_name in wb.sheet_names():
            sheet = wb.sheet_by_name(sheet_name)
            test = self._extract_test(sheet)
            if test.readings:  # Only include tests with data
                tests.append(test)

        return DPSHData(
            expedient=self.expedient,
            tests=tests,
            source_file=str(self.filepath)
        )

    def extract_summary(self) -> dict:
        """
        Extract a summary suitable for report generation.

        Returns:
            Dictionary with key values for the report
        """
        data = self.extract_all()

        summary = {
            'expedient': data.expedient,
            'num_dpsh_tests': data.num_tests,
            'test_ids': data.test_ids,
            'overall_average_n20': round(data.overall_average_n20, 1),
            'water_detected': data.any_water_detected,
            'tests': []
        }

        for test in data.tests:
            test_summary = {
                'id': test.test_id,
                'depth_m': round(test.depth_reached, 2),
                'avg_n20': round(test.average_n20, 1),
                'refusal': test.refusal_reached,
                'water': test.water_detected
            }
            summary['tests'].append(test_summary)

        return summary


# Geotechnical correlations
class GeotechCorrelations:
    """
    Standard correlations for deriving geotechnical parameters from N values.
    These are approximate correlations from geotechnical literature.

    Note: G3DT may use slightly different correlations in their Base de càlcul.
    These should be validated against their actual practice.
    """

    @staticmethod
    def n20_to_n30(n20: float, correction: float = 0.83) -> float:
        """
        Convert N20 (DPSH) to equivalent N30 (SPT).
        This is an approximation; actual conversion depends on soil type.
        """
        # NB = N20 / 0.83 is roughly equivalent to N30 for many soils
        return n20 / correction

    @staticmethod
    def n_to_friction_angle(n: float, soil_type: str = 'granular') -> float:
        """
        Estimate friction angle (φ) from N value.

        Based on Peck, Hanson & Thornburn correlations for sands/gravels.

        Args:
            n: SPT N value (or equivalent)
            soil_type: 'granular' or 'cohesive'

        Returns:
            Friction angle in degrees
        """
        if soil_type == 'cohesive':
            # For clays, friction angle is less dependent on N
            return 25.0  # Typical value, should use lab tests

        # Granular soils (sands, gravels)
        if n < 4:
            return 28.0
        elif n < 10:
            return 30.0
        elif n < 30:
            return 33.0 + (n - 10) * 0.25  # Linear interpolation
        elif n < 50:
            return 38.0
        else:
            return 40.0  # Maximum typical value

    @staticmethod
    def n_to_deformation_modulus(n: float, soil_type: str = 'granular') -> float:
        """
        Estimate deformation modulus (E) from N value.

        Various correlations exist; this uses a common approximation.

        Args:
            n: SPT N value (or equivalent)
            soil_type: 'granular' or 'cohesive'

        Returns:
            Deformation modulus in kg/cm²
        """
        if soil_type == 'cohesive':
            # For clays: E ≈ 5-10 × N (kg/cm²)
            return 7 * n

        # Granular soils: E ≈ 10-15 × N (kg/cm²)
        # Using 10 as conservative estimate
        return 10 * n

    @staticmethod
    def n_to_density(n: float, soil_type: str = 'granular') -> float:
        """
        Estimate soil density from N value.

        Args:
            n: SPT N value
            soil_type: 'granular' or 'cohesive'

        Returns:
            Density in g/cm³
        """
        if soil_type == 'cohesive':
            # Clays typically 1.7-2.0 g/cm³
            if n < 4:
                return 1.7
            elif n < 15:
                return 1.85
            else:
                return 2.0

        # Granular soils
        if n < 10:
            return 1.8  # Loose
        elif n < 30:
            return 1.95  # Medium
        else:
            return 2.1  # Dense

    @staticmethod
    def n_to_relative_density(n: float) -> str:
        """
        Classify relative density from N value.

        Returns:
            Density classification string
        """
        if n < 4:
            return "Molt fluix / Very loose"
        elif n < 10:
            return "Fluix / Loose"
        elif n < 30:
            return "Mig / Medium"
        elif n < 50:
            return "Dens / Dense"
        else:
            return "Molt dens / Very dense"


def _extract_dates_from_pdf(pdf_path: Path, patterns: list[str]) -> set[str]:
    """
    Extract dates from a PDF using the given regex patterns.

    Each pattern must have 3 groups: (day, month, year).

    Returns set of ISO date strings.
    """
    import re

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return set()

    dates: set[str] = set()
    try:
        doc = fitz.open(str(pdf_path))
        for page in doc:
            text = page.get_text()
            for pat in patterns:
                for match in re.finditer(pat, text):
                    day, month, year = match.groups()
                    try:
                        iso_date = f"{year}-{int(month):02d}-{int(day):02d}"
                        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                            dates.add(iso_date)
                    except ValueError:
                        continue
        doc.close()
    except Exception:
        pass

    return dates


def extract_field_dates(project_path: str | Path) -> list[str]:
    """
    Extract field work dates from all available project PDFs.

    Sources (in order):
    1. DPSH PDF: "DATA: dd/mm/yyyy" (DPSH test dates)
    2. Lab PDF: "Data extracció: dd/mm/yyyy" (sample extraction date = sondeig date)

    Args:
        project_path: Path to the project folder

    Returns:
        Sorted list of unique ISO date strings (e.g., ['2025-10-01', '2025-10-06'])
        Empty list if no PDFs found or no dates extracted.
    """
    project_path = Path(project_path)
    dates: set[str] = set()

    # Source 1: DPSH PDF — "DATA: dd/mm/yyyy"
    dpsh_patterns = [r'DATA:\s*(\d{1,2})/(\d{1,2})/(\d{4})']
    for glob_pat in ('PDF/ANNEXES/*_DPSH.pdf', 'ANNEXES/*_DPSH.pdf', '*_DPSH.pdf'):
        candidates = list(project_path.glob(glob_pat))
        if candidates:
            dates |= _extract_dates_from_pdf(candidates[0], dpsh_patterns)
            break

    # Source 2: Lab PDF — only the earliest date (= "Data extracció" = field date)
    # Lab PDFs contain multiple dates (extracció, recepció, realització, expedició).
    # The earliest is always the field extraction date; later ones are lab-internal.
    lab_all_patterns = [r'(\d{1,2})/(\d{1,2})/(\d{4})']
    for glob_pat in ('PDF/ANNEXES/LAB*.pdf', 'PDF/ANNEXES/lab*.pdf', 'ANNEXES/LAB*.pdf'):
        candidates = list(project_path.glob(glob_pat))
        if candidates:
            lab_dates = _extract_dates_from_pdf(candidates[0], lab_all_patterns)
            if lab_dates:
                dates.add(min(lab_dates))  # Earliest = field extraction date
            break

    return sorted(dates)


_FIRST_DAY_SAME_MONTH_RE = re.compile(r"^\s*(\d{1,2})(?:\s*,\s*\d{1,2})*\s+i\s+\d{1,2}\s+(d['’]\s*|de\s+)(\w+)\s+de\s+(\d{4})\s*$")
_FIRST_DAY_MULTI_MONTH_RE = re.compile(r"^\s*(\d{1,2}\s+(?:d['’]\s*|de\s+)\w+)\s*(?:,|\s+i\s+).*?\s+de\s+(\d{4})\s*$")


def first_field_day_text(dates: list[str] | None, text: str | None) -> str:
    """Text catala del PRIMER dia de camp, per a la primera ranura de l'informe («El dia 1 d'octubre de 2025, es va
    visitar l'obra»); la segona ranura («la campanya de camp, que s'ha realitzat el dia 1 i 6 d'octubre de 2025») porta
    tots els dies (`format_dates_catalan`). Decisio del Josep 2026-09-05: els informes signats (Bell-lloc) ho fan aixi.

    Amb la llista de dates ISO, es formata la mes antiga; sense llista, es deriva del text ja formatat («1 i 6
    d'octubre de 2025» → «1 d'octubre de 2025»; «1 d'octubre i 15 de novembre de 2025» → «1 d'octubre de 2025»); si el
    text no te aquesta forma, es torna tal qual (mai buit si hi havia text)."""
    if dates:
        try:
            return format_dates_catalan([sorted(str(d) for d in dates)[0]])
        except (ValueError, IndexError):
            pass
    text = (text or "").strip()
    m = _FIRST_DAY_SAME_MONTH_RE.match(text)
    if m:
        prefix = "d'" if m.group(2).strip().startswith(("d'", "d\u2019")) else "de "
        return f"{m.group(1)} {prefix}{m.group(3)} de {m.group(4)}"
    m = _FIRST_DAY_MULTI_MONTH_RE.match(text)
    if m:
        return f"{m.group(1)} de {m.group(2)}"
    return text


def format_dates_catalan(dates: list[str]) -> str:
    """
    Format ISO date list as Catalan text for the report.

    Examples:
        ['2025-10-01'] -> "1 d'octubre de 2025"
        ['2025-10-01', '2025-10-06'] -> "1 i 6 d'octubre de 2025"
        ['2025-10-01', '2025-11-15'] -> "1 d'octubre i 15 de novembre de 2025"

    Args:
        dates: Sorted list of ISO date strings

    Returns:
        Catalan formatted text, or empty string if no dates
    """
    if not dates:
        return ''

    MESOS = {
        1: 'gener', 2: 'febrer', 3: 'març', 4: 'abril',
        5: 'maig', 6: 'juny', 7: 'juliol', 8: 'agost',
        9: 'setembre', 10: 'octubre', 11: 'novembre', 12: 'desembre',
    }

    # Catalan: months starting with vowel use "d'" prefix, consonant use "de "
    VOWEL_MONTHS = {4, 8, 10}  # abril, agost, octubre

    parsed = []
    for d in dates:
        parts = d.split('-')
        parsed.append((int(parts[0]), int(parts[1]), int(parts[2])))

    if len(parsed) == 1:
        y, m, d = parsed[0]
        prefix = "d'" if m in VOWEL_MONTHS else "de "
        return f"{d} {prefix}{MESOS[m]} de {y}"

    # Check if all dates are in the same month and year
    same_month = all(p[0] == parsed[0][0] and p[1] == parsed[0][1] for p in parsed)

    if same_month:
        y, m, _ = parsed[0]
        days = [str(p[2]) for p in parsed]
        if len(days) == 2:
            days_text = f"{days[0]} i {days[1]}"
        else:
            days_text = ', '.join(days[:-1]) + f' i {days[-1]}'
        prefix = "d'" if m in VOWEL_MONTHS else "de "
        return f"{days_text} {prefix}{MESOS[m]} de {y}"

    # Different months - format each date
    parts = []
    for y, m, d in parsed:
        prefix = "d'" if m in VOWEL_MONTHS else "de "
        parts.append(f"{d} {prefix}{MESOS[m]}")

    if len(parts) == 2:
        text = f"{parts[0]} i {parts[1]}"
    else:
        text = ', '.join(parts[:-1]) + f' i {parts[-1]}'

    # Add year (assuming same year for all)
    return f"{text} de {parsed[0][0]}"


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: uv run --with xlrd dpsh_extractor.py <path_to_dpsh.xls> [--json]")
        print("\nExample:")
        print("  uv run --with xlrd dpsh_extractor.py reference-material/4001612-bell-lloc/ANNEXES/4001612_DPSH.xls")
        sys.exit(1)

    filepath = sys.argv[1]
    output_json = '--json' in sys.argv

    try:
        extractor = DPSHExtractor(filepath)
        data = extractor.extract_all()

        if output_json:
            print(data.to_json())
        else:
            # Human-readable output
            print(f"\n{'='*60}")
            print(f"DPSH Extraction Results: {data.expedient}")
            print(f"{'='*60}")
            print(f"Source: {data.source_file}")
            print(f"Number of tests: {data.num_tests}")
            print(f"Test IDs: {', '.join(data.test_ids)}")
            print(f"Overall average N₂₀: {data.overall_average_n20:.1f}")
            print(f"Water detected: {'Yes' if data.any_water_detected else 'No'}")

            for test in data.tests:
                print(f"\n{'-'*40}")
                print(f"Test: {test.test_id}")
                print(f"  Correction factor: {test.correction_factor}")
                print(f"  Depth reached: {test.depth_reached:.2f} m")
                print(f"  Average N₂₀: {test.average_n20:.1f}")
                print(f"  Refusal: {'Yes' if test.refusal_reached else 'No'}", end='')
                if test.refusal_depth:
                    print(f" (at {abs(test.refusal_depth):.2f} m)")
                else:
                    print()
                print(f"  Water: {'Yes' if test.water_detected else 'No'}", end='')
                if test.water_depth:
                    print(f" (at {abs(test.water_depth):.2f} m)")
                else:
                    print()

                # Show readings table
                print(f"\n  {'Depth (m)':<10} {'N₂₀':<6} {'NB':<8}")
                print(f"  {'-'*24}")
                for r in test.readings:
                    print(f"  {abs(r.depth_m):<10.2f} {r.n20:<6} {r.nb:<8.2f}")

                # Show correlations
                avg_n = test.average_n20
                print(f"\n  Derived parameters (correlations):")
                print(f"    φ (friction angle): {GeotechCorrelations.n_to_friction_angle(avg_n):.0f}°")
                print(f"    E (deformation modulus): {GeotechCorrelations.n_to_deformation_modulus(avg_n):.0f} kg/cm²")
                print(f"    γ (density): {GeotechCorrelations.n_to_density(avg_n):.2f} g/cm³")
                print(f"    Relative density: {GeotechCorrelations.n_to_relative_density(avg_n)}")

            print(f"\n{'='*60}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error extracting DPSH data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
