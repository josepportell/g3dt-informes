#!/usr/bin/env python3
"""
G3DT Project Data Extractor

Extracts all available data from a G3DT project folder structure.
Combines data from multiple sources into a unified structure for report generation.

Sources extracted:
- Folder name → expedient, municipality
- DADES CLIENT.txt → client information
- DPSH.xls → penetration test data
- File inventory → test types performed

Usage:
    uv run --with xlrd project_extractor.py <path_to_project_folder>

Author: Eficients.cat
Date: 2026-02-02
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .dpsh_extractor import DPSHExtractor, DPSHData, GeotechCorrelations


@dataclass
class ClientData:
    """Client information extracted from DADES CLIENT.txt"""
    company_name: str = ""
    nif: str = ""
    representative: str = ""
    representative_nif: str = ""
    address: str = ""
    postal_code: str = ""
    city: str = ""
    phone: str = ""
    email: str = ""

    @classmethod
    def from_file(cls, filepath: Path) -> 'ClientData':
        """
        Parse DADES CLIENT.txt file.

        Expected format:
        ```
        DADES CLIENT
        COMPANY NAME       NIF
        Representant:
        REPRESENTATIVE NAME   NIF
        Address line
        POSTAL CITY
        T. phone
        E. email
        ```
        """
        if not filepath.exists():
            return cls()

        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            lines = [l.strip() for l in content.split('\n') if l.strip()]

            client = cls()

            for i, line in enumerate(lines):
                # Skip header
                if 'DADES CLIENT' in line.upper():
                    continue

                # Company line (usually has NIF after name)
                if i == 1 or (i > 0 and 'DADES CLIENT' in lines[i-1].upper()):
                    # Try to split company name and NIF
                    parts = line.split()
                    # NIF pattern: letter + 8 digits or 8 digits + letter
                    nif_pattern = r'[A-Z]\d{8}|\d{8}[A-Z]'
                    for j, part in enumerate(parts):
                        if re.match(nif_pattern, part):
                            client.company_name = ' '.join(parts[:j])
                            client.nif = part
                            break
                    else:
                        client.company_name = line
                    continue

                # Representative
                if 'representant' in line.lower():
                    continue  # Skip the "Representant:" label
                if client.company_name and not client.representative and i > 2:
                    # Check for NIF in this line too
                    parts = line.split()
                    nif_pattern = r'\d{8}[A-Z]'
                    for j, part in enumerate(parts):
                        if re.match(nif_pattern, part):
                            client.representative = ' '.join(parts[:j])
                            client.representative_nif = part
                            break
                    else:
                        client.representative = line
                    continue

                # Address (line starting with Carrer, Avinguda, C/, etc.)
                if re.match(r'^(carrer|c/|avinguda|av\.|plaça|pl\.)', line.lower()):
                    client.address = line
                    continue

                # Postal code + city (5 digits followed by city name)
                postal_match = re.match(r'^(\d{5})\s+(.+)$', line)
                if postal_match:
                    client.postal_code = postal_match.group(1)
                    client.city = postal_match.group(2)
                    continue

                # Phone
                if line.upper().startswith('T.') or line.upper().startswith('TEL'):
                    client.phone = re.sub(r'^T\.?\s*', '', line, flags=re.IGNORECASE).strip()
                    continue

                # Email
                if line.upper().startswith('E.') or '@' in line:
                    client.email = re.sub(r'^E\.?\s*', '', line, flags=re.IGNORECASE).strip()
                    continue

            return client

        except Exception as e:
            print(f"Warning: Error parsing DADES CLIENT.txt: {e}", file=sys.stderr)
            return cls()


@dataclass
class FileInventory:
    """Inventory of files found in the project folder."""
    has_dpsh_excel: bool = False
    has_sondeig: bool = False
    has_dpsh_pdf: bool = False
    has_sondeig_pdf: bool = False
    has_photos: bool = False
    has_lab_request: bool = False
    has_lab_results: bool = False
    has_cover: bool = False

    dpsh_excel_path: Optional[str] = None
    sondeig_path: Optional[str] = None
    lab_request_path: Optional[str] = None
    lab_results_path: Optional[str] = None
    photo_paths: list = field(default_factory=list)


@dataclass
class ProjectData:
    """Complete extracted data for a G3DT project."""
    # Project identification
    expedient: str = ""
    municipality: str = ""
    folder_path: str = ""

    # Client data
    client: ClientData = field(default_factory=ClientData)

    # DPSH data
    dpsh: Optional[DPSHData] = None

    # File inventory
    files: FileInventory = field(default_factory=FileInventory)

    # Derived/calculated values
    cte_classification: str = ""  # Will be set based on building data
    num_soil_levels: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            'project': {
                'expedient': self.expedient,
                'municipality': self.municipality,
                'folder_path': self.folder_path,
            },
            'client': {
                'company_name': self.client.company_name,
                'nif': self.client.nif,
                'representative': self.client.representative,
                'address': self.client.address,
                'postal_code': self.client.postal_code,
                'city': self.client.city,
                'phone': self.client.phone,
                'email': self.client.email,
            },
            'files': {
                'has_dpsh_excel': self.files.has_dpsh_excel,
                'has_sondeig': self.files.has_sondeig,
                'has_photos': self.files.has_photos,
                'has_lab_request': self.files.has_lab_request,
                'has_lab_results': self.files.has_lab_results,
                'photo_count': len(self.files.photo_paths),
            },
            'dpsh': self.dpsh.to_dict() if self.dpsh else None,
        }

        # Add derived geotechnical parameters if DPSH data available
        if self.dpsh and self.dpsh.tests:
            avg_n20 = self.dpsh.overall_average_n20
            result['geotechnical'] = {
                'average_n20': round(avg_n20, 1),
                'friction_angle_deg': round(GeotechCorrelations.n_to_friction_angle(avg_n20), 0),
                'deformation_modulus_kg_cm2': round(GeotechCorrelations.n_to_deformation_modulus(avg_n20), 0),
                'density_g_cm3': round(GeotechCorrelations.n_to_density(avg_n20), 2),
                'relative_density': GeotechCorrelations.n_to_relative_density(avg_n20),
            }

        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class ProjectExtractor:
    """
    Extracts all available data from a G3DT project folder.

    Expected folder structure:
    ```
    {expedient} {POBLACIO}/
    ├── ACCEPTACIO/
    │   └── DADES CLIENT.txt
    ├── ANNEXES/
    │   ├── {expedient}_DPSH.xls
    │   └── {expedient}_sondeig.FH11
    ├── FOTOGRAFIES/
    │   ├── DPSH/
    │   └── SONDEIG/
    ├── PDF/
    │   └── ANNEXES/
    │       └── LAB-SIG.pdf
    └── comanda laboratori_{expedient}_{poblacio}.xls
    ```
    """

    def __init__(self, folder_path: str):
        """
        Initialize extractor with path to project folder.

        Args:
            folder_path: Path to the project folder
        """
        self.folder_path = Path(folder_path)
        if not self.folder_path.exists():
            raise FileNotFoundError(f"Project folder not found: {folder_path}")
        if not self.folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")

        # Extract expedient and municipality from folder name
        # Supports both "4001612 BELL-LLOC" and "4001612-bell-lloc" formats
        folder_name = self.folder_path.name

        # Try space-separated first (original format)
        if ' ' in folder_name:
            parts = folder_name.split(maxsplit=1)
            self.expedient = parts[0]
            self.municipality = parts[1].replace('-', ' ').title() if len(parts) > 1 else ""
        # Try hyphen after expedient number
        elif '-' in folder_name:
            # Find where the number ends
            match = re.match(r'^(\d+)[_-](.+)$', folder_name)
            if match:
                self.expedient = match.group(1)
                self.municipality = match.group(2).replace('-', ' ').title()
            else:
                self.expedient = folder_name
                self.municipality = ""
        else:
            self.expedient = folder_name
            self.municipality = ""

    def _find_files(self) -> FileInventory:
        """Scan folder structure and inventory available files."""
        inv = FileInventory()

        # Check ANNEXES folder
        annexes = self.folder_path / 'ANNEXES'
        if annexes.exists():
            for f in annexes.iterdir():
                name_lower = f.name.lower()
                if 'dpsh' in name_lower and f.suffix.lower() == '.xls':
                    inv.has_dpsh_excel = True
                    inv.dpsh_excel_path = str(f)
                if 'sondeig' in name_lower and f.suffix.lower() in ['.fh11', '.pdf']:
                    inv.has_sondeig = True
                    inv.sondeig_path = str(f)

        # Check PDF/ANNEXES folder
        pdf_annexes = self.folder_path / 'PDF' / 'ANNEXES'
        if pdf_annexes.exists():
            for f in pdf_annexes.iterdir():
                name_lower = f.name.lower()
                if 'dpsh' in name_lower and f.suffix.lower() == '.pdf':
                    inv.has_dpsh_pdf = True
                if 'sondeig' in name_lower and f.suffix.lower() == '.pdf':
                    inv.has_sondeig_pdf = True
                if 'lab' in name_lower and f.suffix.lower() == '.pdf':
                    inv.has_lab_results = True
                    inv.lab_results_path = str(f)

        # Check for photos
        fotos = self.folder_path / 'FOTOGRAFIES'
        if fotos.exists():
            inv.has_photos = True
            for subdir in ['DPSH', 'SONDEIG', '']:
                photo_dir = fotos / subdir if subdir else fotos
                if photo_dir.exists():
                    for f in photo_dir.iterdir():
                        if f.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                            inv.photo_paths.append(str(f))

        # Check for lab request
        for f in self.folder_path.iterdir():
            if 'comanda' in f.name.lower() and 'laboratori' in f.name.lower():
                inv.has_lab_request = True
                inv.lab_request_path = str(f)
                break

        # Check for cover
        for f in self.folder_path.iterdir():
            if 'portada' in f.name.lower():
                inv.has_cover = True
                break

        return inv

    def _extract_client(self) -> ClientData:
        """Extract client data from DADES CLIENT.txt"""
        client_file = self.folder_path / 'ACCEPTACIO' / 'DADES CLIENT.txt'
        return ClientData.from_file(client_file)

    def _extract_dpsh(self, inventory: FileInventory) -> Optional[DPSHData]:
        """
        Extract DPSH data, prioritizing approved validation files.

        Priority order:
        1. validation/dpsh_approved.json (if exists and status is approved)
        2. Excel file extraction (fallback)

        Args:
            inventory: FileInventory with file locations

        Returns:
            DPSHData if available from either source, None otherwise
        """
        # First, check for approved validation file
        from .report_data import load_validated_dpsh
        validated_dpsh = load_validated_dpsh(self.folder_path)
        if validated_dpsh:
            print(f"Using approved validation data from validation/dpsh_approved.json",
                  file=sys.stderr)
            return validated_dpsh

        # Fallback to Excel extraction
        if not inventory.has_dpsh_excel or not inventory.dpsh_excel_path:
            return None

        try:
            extractor = DPSHExtractor(inventory.dpsh_excel_path)
            return extractor.extract_all()
        except Exception as e:
            print(f"Warning: Error extracting DPSH data: {e}", file=sys.stderr)
            return None

    def extract_all(self) -> ProjectData:
        """
        Extract all available data from the project folder.

        Returns:
            ProjectData object with all extracted information
        """
        # Scan for files first
        inventory = self._find_files()

        # Extract data from various sources
        client = self._extract_client()
        dpsh = self._extract_dpsh(inventory)

        return ProjectData(
            expedient=self.expedient,
            municipality=self.municipality,
            folder_path=str(self.folder_path),
            client=client,
            dpsh=dpsh,
            files=inventory,
        )


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: uv run --with xlrd project_extractor.py <path_to_project_folder> [--json]")
        print("\nExample:")
        print("  uv run --with xlrd project_extractor.py 'reference-material/4001612-bell-lloc'")
        sys.exit(1)

    folder_path = sys.argv[1]
    output_json = '--json' in sys.argv

    try:
        extractor = ProjectExtractor(folder_path)
        data = extractor.extract_all()

        if output_json:
            print(data.to_json())
        else:
            # Human-readable output
            print(f"\n{'='*60}")
            print(f"Project Data Extraction: {data.expedient}")
            print(f"{'='*60}")

            print(f"\n📁 PROJECT")
            print(f"  Expedient: {data.expedient}")
            print(f"  Municipality: {data.municipality}")
            print(f"  Folder: {data.folder_path}")

            print(f"\n👤 CLIENT")
            print(f"  Company: {data.client.company_name}")
            print(f"  NIF: {data.client.nif}")
            print(f"  Representative: {data.client.representative}")
            print(f"  Address: {data.client.address}")
            print(f"  City: {data.client.postal_code} {data.client.city}")
            print(f"  Phone: {data.client.phone}")
            print(f"  Email: {data.client.email}")

            print(f"\n📄 FILES FOUND")
            print(f"  DPSH Excel: {'✓' if data.files.has_dpsh_excel else '✗'}")
            print(f"  Sondeig: {'✓' if data.files.has_sondeig else '✗'}")
            print(f"  Photos: {'✓' if data.files.has_photos else '✗'} ({len(data.files.photo_paths)} files)")
            print(f"  Lab request: {'✓' if data.files.has_lab_request else '✗'}")
            print(f"  Lab results: {'✓' if data.files.has_lab_results else '✗'}")

            if data.dpsh:
                print(f"\n🔬 DPSH DATA")
                print(f"  Tests: {data.dpsh.num_tests} ({', '.join(data.dpsh.test_ids)})")
                print(f"  Average N₂₀: {data.dpsh.overall_average_n20:.1f}")
                print(f"  Water detected: {'Yes' if data.dpsh.any_water_detected else 'No'}")

                for test in data.dpsh.tests:
                    print(f"\n  {test.test_id}:")
                    print(f"    Depth: {test.depth_reached:.2f} m")
                    print(f"    Avg N₂₀: {test.average_n20:.1f}")
                    print(f"    Refusal: {'Yes' if test.refusal_reached else 'No'}")

                print(f"\n📊 DERIVED PARAMETERS (correlations)")
                avg_n = data.dpsh.overall_average_n20
                print(f"  φ (friction angle): {GeotechCorrelations.n_to_friction_angle(avg_n):.0f}°")
                print(f"  E (deformation modulus): {GeotechCorrelations.n_to_deformation_modulus(avg_n):.0f} kg/cm²")
                print(f"  γ (density): {GeotechCorrelations.n_to_density(avg_n):.2f} g/cm³")
                print(f"  Relative density: {GeotechCorrelations.n_to_relative_density(avg_n)}")

            print(f"\n{'='*60}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error extracting project data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
