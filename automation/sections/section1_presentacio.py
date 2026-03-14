#!/usr/bin/env python3
"""
G3DT Section 1 Generator: PRESENTACIO DE L'ESTUDI

Generates content for the first section of geotechnical reports.
Section 1 contains:
  1.1 ANTECEDENTS - Client info, building data, location
  1.2 CLASSIFICACIO CTE - Building/soil classification per CTE DB SE-C
  1.3 OBJECTIUS - Standard study objectives (static text)

Author: Eficients.cat
Date: 2026-02-03
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..report_data import ReportData

from ..formatting import format_floor_notation


@dataclass
class Section1Content:
    """Generated content for Section 1."""
    intro_paragraph: str
    antecedents_paragraph: str
    taula1: dict[str, str]
    location_paragraph: str
    figure_paths: list[str]
    cte_intro: str
    taula2: dict[str, str]
    objectius: str


class Section1Generator:
    """Generates Section 1: PRESENTACIO DE L'ESTUDI."""

    # Static text for CTE classification intro
    CTE_INTRO_TEXT = (
        "Segons el CTE DB SE-C (Document Basic Seguretat Estructural - Ciments), "
        "la classificacio del projecte es determina en funcio de les caracteristiques "
        "de l'edifici (tipus de construccio C) i del terreny (tipus de terreny T)."
    )

    # Static text for objectives section
    OBJECTIUS_TEXT = (
        "L'objectiu del present estudi geotecnic es el de determinar les "
        "caracteristiques del terreny on es preveu realitzar la construccio, "
        "amb la finalitat de:\n\n"
        "- Definir les caracteristiques geotecniques del subsol.\n"
        "- Establir el perfil estratigrafic del terreny.\n"
        "- Determinar la presencia o absencia de nivell freatic.\n"
        "- Calcular la capacitat portant admissible del terreny.\n"
        "- Recomanar el tipus de fonamentacio mes adequat.\n"
        "- Definir els parametres geotecnics necessaris per al disseny de la fonamentacio."
    )

    # Fallback text for missing required fields
    FALLBACK_CLIENT = "[Client no especificat]"
    FALLBACK_ARCHITECT = "[Arquitecte no especificat]"
    FALLBACK_ARCHITECT_COMPANY = "[Empresa no especificada]"
    FALLBACK_VALUE = "-"

    def __init__(self, data: ReportData):
        """
        Initialize generator with report data.

        Args:
            data: ReportData instance with all project information
        """
        self.data = data

    def _get_client_name(self) -> str:
        """Get client company name with fallback."""
        name = getattr(self.data.client, 'company_name', None)
        return name.strip() if name and name.strip() else self.FALLBACK_CLIENT

    def _get_architect_name(self) -> str:
        """Get architect name with fallback."""
        name = getattr(self.data, 'architect_name', None)
        return name.strip() if name and name.strip() else self.FALLBACK_ARCHITECT

    def _get_architect_company(self) -> str:
        """Get architect company with fallback."""
        company = getattr(self.data, 'architect_company', None)
        return company.strip() if company and company.strip() else self.FALLBACK_ARCHITECT_COMPANY

    def _safe_value(self, value: str | None) -> str:
        """Return value or fallback for table display."""
        if value and str(value).strip():
            return str(value).strip()
        return self.FALLBACK_VALUE

    def generate_intro_paragraph(self) -> str:
        """
        Generate the client introduction paragraph.

        Returns:
            Formatted introduction paragraph with client name
        """
        return f"A peticio de:\n\n{self._get_client_name().upper()},"

    def generate_antecedents_paragraph(self) -> str:
        """
        Generate the background/antecedents paragraph.

        Returns:
            Formatted paragraph describing the project background
        """
        # Build building description
        building_desc = self._build_building_description()

        return (
            f"Segons ens indica el sol.licitant, el SR. {self._get_architect_name().upper()}, "
            f"de {self._get_architect_company().upper()}, en nom de {self._get_client_name().upper()}, "
            f"es preveu la construccio de {building_desc}."
        )

    def _build_building_description(self) -> str:
        """Build description of the construction project."""
        parts = []

        # Building type
        if self.data.building_type:
            parts.append(self.data.building_type.lower())
        else:
            parts.append("una edificacio")

        # Number of floors
        if self.data.num_floors:
            parts.append(f"de {format_floor_notation(self.data.num_floors)}")

        # Basement mention
        if self.data.has_basement:
            parts.append("amb soterrani")

        return " ".join(parts)

    def generate_taula1(self) -> dict[str, str]:
        """
        Generate Table 1: Building specifications.

        Returns:
            Dictionary with building data for table rendering
        """
        # Format basement description
        if self.data.has_basement:
            soterrani = "1 soterrani"
        else:
            soterrani = "Cap"

        # Format foundation type
        fonamentacio = "Fonaments superficials"
        if self.data.has_basement or self.data.has_retaining_walls:
            fonamentacio = "Fonaments superficials i murs de contencio"

        return {
            "Tipus de construccio": self._safe_value(self.data.building_type),
            "Num. de plantes": self._safe_value(format_floor_notation(self.data.num_floors) if self.data.num_floors else None),
            "Superficie parcela": f"{self.data.superficie_parcela} m2" if self.data.superficie_parcela else self.FALLBACK_VALUE,
            "Superficie construida": f"{self.data.superficie_construida} m2" if self.data.superficie_construida else self.FALLBACK_VALUE,
            "Tipus fonamentacio": fonamentacio,
            "Soterranis": soterrani,
        }

    def generate_location_paragraph(self) -> str:
        """
        Generate the location description paragraph.

        Returns:
            Formatted paragraph with project location
        """
        parts = ["L'emplacament del projecte es situa"]

        # Street address
        if self.data.street_address:
            parts.append(f"al {self.data.street_address}")

        # Municipality
        if self.data.municipality:
            parts.append(f"al terme municipal de {self.data.municipality}")

        parts_text = " ".join(parts) + "."

        # Add UTM coordinates if available
        if self.data.utm_x and self.data.utm_y:
            parts_text += (
                f"\n\nLes coordenades UTM (ETRS89, fus 31N) del solar son aproximadament:\n"
                f"X: {self.data.utm_x:.0f} m\n"
                f"Y: {self.data.utm_y:.0f} m"
            )

        return parts_text

    def get_figure_paths(self) -> list[str]:
        """
        Get list of figure paths for Section 1.

        Returns:
            List of figure path placeholders (to be filled with actual paths)
        """
        figures = [
            "[FIGURA 1: Situacio ICGC - Vista general]",
            "[FIGURA 2: Situacio ICGC - Vista detall]",
        ]

        # Figure 3 is conditional (architect plans)
        figures.append("[FIGURA 3: Planol de l'arquitecte (opcional)]")

        return figures

    def generate_cte_intro(self) -> str:
        """
        Generate CTE classification intro (static).

        Returns:
            Static introductory text for CTE classification section
        """
        return self.CTE_INTRO_TEXT

    def generate_taula2(self) -> dict[str, str]:
        """
        Generate Table 2: CTE classification.

        Returns:
            Dictionary with CTE classification data for table rendering
        """
        # Get building class description
        building_desc = self._get_building_class_description()
        soil_desc = self._get_soil_class_description()

        return {
            "Tipus de construccio (C)": f"{self.data.cte_building_class} - {building_desc}",
            "Tipus de terreny (T)": f"{self.data.cte_soil_class} - {soil_desc}",
        }

    def _get_building_class_description(self) -> str:
        """Get description for building class."""
        descriptions = {
            "C-0": "Construccions d'importancia menor",
            "C-1": "Altres construccions",
            "C-2": "Construccions especials",
        }
        return descriptions.get(self.data.cte_building_class, "No classificat")

    def _get_soil_class_description(self) -> str:
        """Get description for soil class."""
        descriptions = {
            "T-1": "Terrenys favorables",
            "T-2": "Terrenys intermedis",
            "T-3": "Terrenys desfavorables",
        }
        return descriptions.get(self.data.cte_soil_class, "No classificat")

    def generate_objectius(self) -> str:
        """
        Generate objectives section (static).

        Returns:
            Static objectives text for geotechnical study
        """
        return self.OBJECTIUS_TEXT

    def generate_all(self) -> Section1Content:
        """
        Generate all Section 1 content.

        Returns:
            Section1Content dataclass with all generated content
        """
        return Section1Content(
            intro_paragraph=self.generate_intro_paragraph(),
            antecedents_paragraph=self.generate_antecedents_paragraph(),
            taula1=self.generate_taula1(),
            location_paragraph=self.generate_location_paragraph(),
            figure_paths=self.get_figure_paths(),
            cte_intro=self.generate_cte_intro(),
            taula2=self.generate_taula2(),
            objectius=self.generate_objectius(),
        )


# CLI for testing
if __name__ == '__main__':
    import sys
    from pathlib import Path
    from datetime import date
    from dataclasses import dataclass, field

    # For standalone testing, define minimal data classes
    # (avoids import issues when running directly)
    @dataclass
    class ClientData:
        company_name: str
        contact_name: str | None = None
        nif: str | None = None
        address: str | None = None

    @dataclass
    class ReportData:
        expedient: str
        municipality: str
        report_date: date
        client: ClientData
        architect_name: str
        architect_company: str
        building_type: str
        num_floors: str
        superficie_parcela: str
        superficie_construida: str
        has_basement: bool
        has_retaining_walls: bool
        street_address: str
        utm_x: float | None = None
        utm_y: float | None = None
        cte_building_class: str = "C-0"
        cte_soil_class: str = "T-1"

    print("=" * 60)
    print("G3DT Section 1 Generator - Test")
    print("=" * 60)

    # Create test data
    client = ClientData(
        company_name="Construccions Exemple SL",
        contact_name="Pere Garcia",
        nif="B12345678",
    )

    test_data = ReportData(
        expedient="4001612",
        municipality="Bell-lloc d'Urgell",
        report_date=date.today(),
        client=client,
        architect_name="Joan Arquitecte",
        architect_company="Arquitectura i Disseny SLP",
        building_type="Habitatge unifamiliar aillat",
        num_floors="Pb + 1Pp",
        superficie_parcela="450",
        superficie_construida="220",
        has_basement=False,
        has_retaining_walls=False,
        street_address="Carrer Mestre Ramon Ortiz, s/n",
        utm_x=307500.0,
        utm_y=4610200.0,
        cte_building_class="C-0",
        cte_soil_class="T-1",
    )

    # Generate content
    generator = Section1Generator(test_data)
    content = generator.generate_all()

    # Display results
    print("\n" + "-" * 60)
    print("1.1 ANTECEDENTS")
    print("-" * 60)

    print("\n[Intro Paragraph]")
    print(content.intro_paragraph)

    print("\n[Antecedents Paragraph]")
    print(content.antecedents_paragraph)

    print("\n[Taula 1: Dades de l'edificacio]")
    for key, value in content.taula1.items():
        print(f"  {key}: {value}")

    print("\n[Location Paragraph]")
    print(content.location_paragraph)

    print("\n[Figures]")
    for fig in content.figure_paths:
        print(f"  - {fig}")

    print("\n" + "-" * 60)
    print("1.2 CLASSIFICACIO CTE")
    print("-" * 60)

    print("\n[CTE Intro]")
    print(content.cte_intro)

    print("\n[Taula 2: Classificacio CTE]")
    for key, value in content.taula2.items():
        print(f"  {key}: {value}")

    print("\n" + "-" * 60)
    print("1.3 OBJECTIUS")
    print("-" * 60)
    print(content.objectius)

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
