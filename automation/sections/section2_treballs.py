#!/usr/bin/env python3
"""
G3DT Section 2 Generator: TREBALLS DE CAMP

Generates content for the field work section of geotechnical reports.
Section 2 contains:
  2.1 DESCRIPCIO ZONA - Site visit, adjacent parcels, site description
  2.2 RECONEIXEMENT DEL TERRENY - Test dates, test list, lab accreditation
  2.3 JUSTIFICACIO CTE - Static regulatory text
  2.4 ASSAIGS IN SITU - DPSH, Sondeig (conditional), SPT (conditional), tables
  2.5 ASSAIGS LABORATORI - Lab test introduction and table

Author: Eficients.cat
Date: 2026-02-03
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..report_data import ReportData


@dataclass
class Section2Content:
    """Generated content for Section 2."""
    # 2.1 DESCRIPCIO ZONA
    visit_date_paragraph: str
    visit_objectives: str
    adjacent_parcels_paragraph: str
    site_description_paragraph: str
    photo_references: list[str]

    # 2.2 RECONEIXEMENT DEL TERRENY
    test_dates_paragraph: str
    test_list: list[str]
    lab_accreditation: str

    # 2.3 JUSTIFICACIO CTE
    cte_justification: str

    # 2.4 ASSAIGS IN SITU
    dpsh_description: str
    sondeig_description: str | None  # None if no sondeig
    spt_description: str | None  # None if no SPT
    taula3_dpsh: list[dict[str, str]]
    taula4_sondeig: list[dict[str, str]] | None  # None if no sondeig
    taula5_spt: list[dict[str, str]] | None  # None if no SPT

    # 2.5 ASSAIGS LABORATORI
    lab_intro: str
    taula6_lab: list[dict[str, str]]


class Section2Generator:
    """Generates Section 2: TREBALLS DE CAMP."""

    # Static text for visit objectives
    VISIT_OBJECTIVES = (
        "- Comprovar que els terrenys son aptes per a l'emplacament previst.\n"
        "- Identificar les formacions geologiques presents.\n"
        "- Localitzar els punts de reconeixement i determinar-ne l'accessibilitat.\n"
        "- Observar les condicions hidrologiques del terreny."
    )

    # Static text for lab accreditation
    LAB_ACCREDITATION = (
        "Els assaigs de laboratori s'han realitzat al Laboratori d'Assaigs "
        "de G3DT, acreditat per la Generalitat de Catalunya."
    )

    # Static text for CTE justification (2.3)
    CTE_JUSTIFICATION = (
        "D'acord amb l'article 3.2.1 del CTE DB SE-C, el reconeixement del terreny "
        "s'ha de realitzar amb la intensitat i profunditat adequades a les "
        "caracteristiques del projecte i del terreny.\n\n"
        "Per a edificacions de tipus C-0 i C-1 en terrenys T-1 i T-2, "
        "la campanya de reconeixement ha de permetre:\n\n"
        "- Identificar les unitats geotecniques presents.\n"
        "- Determinar la posicio del nivell freatic.\n"
        "- Estimar els parametres resistents del terreny.\n"
        "- Detectar possibles riscos geologics.\n\n"
        "El nombre i distribucio dels punts de reconeixement s'ha determinat "
        "en funcio de la superficie de la parcel·la i la variabilitat esperada "
        "del terreny, complint amb els minims establerts a la normativa."
    )

    # Static text for DPSH description (2.4.1)
    DPSH_DESCRIPTION = (
        "L'assaig de penetracio dinamica superpesada (DPSH) es un assaig in situ "
        "que consisteix en la penetracio d'una punta conica en el terreny mitjancant "
        "cops successius d'una massa de 63.5 kg que cau des d'una alcada de 76 cm.\n\n"
        "Es comptabilitza el nombre de cops necessaris per penetrar cada 20 cm (N20). "
        "Aquest valor permet estimar la resistencia i la compacitat del terreny, "
        "aixi com correlacionar-lo amb parametres geotecnics."
    )

    # Static text for Sondeig description (2.4.2)
    SONDEIG_DESCRIPTION = (
        "El sondeig mecanic a rotacio permet obtenir mostres continues o alternes "
        "del terreny, aixi com realitzar assaigs SPT a diferents profunditats.\n\n"
        "S'utilitza quan es necessita coneixement detallat de l'estratigrafia "
        "o quan la profunditat de reconeixement supera la capacitat dels assaigs "
        "de penetracio dinamica."
    )

    # Static text for SPT description (2.4.3)
    SPT_DESCRIPTION = (
        "L'assaig SPT (Standard Penetration Test) es realitza dins del sondeig "
        "i consisteix en la penetracio d'un culleret normalitzat mitjancant "
        "una massa de 63.5 kg que cau des de 76 cm.\n\n"
        "Es comptabilitza el nombre de cops necessaris per penetrar 30 cm (N30), "
        "despres d'una clavada inicial de 15 cm. Aquest valor permet estimar "
        "la resistencia del terreny i correlacionar-lo amb parametres geotecnics."
    )

    # Static text for lab tests intro (2.5)
    LAB_INTRO = (
        "Amb les mostres obtingudes als reconeixements s'han realitzat els "
        "assaigs de laboratori necessaris per a la caracteritzacio del terreny, "
        "d'acord amb les normes UNE corresponents."
    )

    # Fallback values
    FALLBACK_VALUE = "-"
    FALLBACK_DESCRIPTION = "[Descripcio del terreny]"

    def __init__(self, data: ReportData):
        """
        Initialize generator with report data.

        Args:
            data: ReportData instance with all project information
        """
        self.data = data

    def _safe_value(self, value: str | None) -> str:
        """Return value or fallback for display."""
        if value and str(value).strip():
            return str(value).strip()
        return self.FALLBACK_VALUE

    def _pluralize(self, count: int, singular: str, plural: str) -> str:
        """Return singular or plural form based on count."""
        return singular if count == 1 else plural

    def _get_test_date(self) -> str:
        """Get the date of field tests from DPSH data."""
        if self.data.dpsh and self.data.dpsh.tests:
            return self.data.report_date.strftime("%d/%m/%Y")
        return self.FALLBACK_VALUE

    # === 2.1 DESCRIPCIO ZONA ===

    def generate_visit_date_paragraph(self) -> str:
        """
        Generate the visit date paragraph.

        Returns:
            Formatted paragraph with visit date
        """
        date_str = self._get_test_date()
        return f"El dia {date_str}, es va visitar l'obra per tal de:"

    def generate_visit_objectives(self) -> str:
        """
        Generate the visit objectives list.

        Returns:
            Static objectives list
        """
        return self.VISIT_OBJECTIVES

    def generate_adjacent_parcels(self) -> str:
        """
        Generate the adjacent parcels description (2.1.1).

        Returns:
            Formatted paragraph describing parcel boundaries
        """
        adj = self.data.adjacent_parcels or {}

        # Get values with fallbacks
        north = adj.get('north', '')
        south = adj.get('south', '')
        east = adj.get('east', '')
        west = adj.get('west', '')

        # Build position description
        position = self.data.site_position or "centre"
        shape = self.data.parcel_shape or "rectangular"
        municipality = self.data.municipality or "[municipi]"

        intro = (
            f"La parcel·la objecte d'estudi es situa al {position} "
            f"del municipi de {municipality}, "
            f"pren una morfologia {shape} i limita:"
        )

        limits = []
        if north:
            limits.append(f"Per la part nord amb {north}.")
        if south:
            limits.append(f"Per la part sud amb {south}.")
        if east:
            limits.append(f"Per la part est amb {east}.")
        if west:
            limits.append(f"I finalment, per la part oest, amb {west}.")

        if limits:
            return intro + "\n\n" + "\n".join(limits)
        return intro + "\n\n[Descripcio dels limits de la parcel·la]"

    def generate_site_description(self) -> str:
        """
        Generate the site description paragraph (2.1.2).

        Returns:
            Formatted paragraph describing the site conditions
        """
        parts = []

        # Urban/rural context
        if self.data.is_urban:
            parts.append("La parcel·la es troba en zona urbana consolidada")
        else:
            parts.append("La parcel·la es troba en zona periurbana o rural")

        # Slope
        if self.data.is_sloped:
            parts.append("amb pendent significatiu")
        else:
            parts.append("amb topografia sensiblement plana")

        if parts:
            return ", ".join(parts) + "."

        return self.FALLBACK_DESCRIPTION

    def get_photo_references(self) -> list[str]:
        """
        Get list of photo references for Section 2.

        Returns:
            List of photo reference placeholders
        """
        return [
            "[FOTO 1: Vista general de la parcel·la]",
            "[FOTO 2: Detall del terreny]",
        ]

    # === 2.2 RECONEIXEMENT DEL TERRENY ===

    def generate_test_dates_paragraph(self) -> str:
        """
        Generate the test dates paragraph.

        Returns:
            Formatted paragraph with test execution dates
        """
        date_str = self._get_test_date()
        num_tests = self.data.num_dpsh_tests

        paragraph = f"Els treballs de camp es van realitzar el dia {date_str}."

        if num_tests > 0:
            assaig_word = self._pluralize(num_tests, "assaig", "assaigs")
            paragraph += f" Es van executar {num_tests} {assaig_word} de penetracio dinamica superpesada (DPSH)."

        if self.data.has_sondeig:
            paragraph += " Addicionalment, es va realitzar un sondeig mecanic a rotacio."

        return paragraph

    def generate_test_list(self) -> list[str]:
        """
        Generate the list of tests performed.

        Returns:
            Bullet list of tests performed
        """
        tests = []

        num_dpsh = self.data.num_dpsh_tests
        if num_dpsh > 0:
            assaig_word = self._pluralize(num_dpsh, "assaig", "assaigs")
            tests.append(f"{num_dpsh} {assaig_word} de penetracio dinamica superpesada (DPSH)")

        if self.data.has_sondeig:
            tests.append("1 sondeig mecanic a rotacio")

        if self.data.has_spt:
            tests.append("Assaigs SPT dins del sondeig")

        if not tests:
            tests.append("[Cap assaig registrat]")

        return tests

    def generate_lab_accreditation(self) -> str:
        """
        Generate the lab accreditation text.

        Returns:
            Static lab accreditation text
        """
        return self.LAB_ACCREDITATION

    # === 2.3 JUSTIFICACIO CTE ===

    def generate_cte_justification(self) -> str:
        """
        Generate the CTE justification text.

        Returns:
            Static CTE regulatory justification
        """
        return self.CTE_JUSTIFICATION

    # === 2.4 ASSAIGS IN SITU ===

    def generate_dpsh_description(self) -> str:
        """
        Generate DPSH description with test count.

        Returns:
            DPSH description with specific test count
        """
        num_tests = self.data.num_dpsh_tests
        base_text = self.DPSH_DESCRIPTION

        if num_tests > 0:
            assaig_word = self._pluralize(num_tests, "assaig", "assaigs")
            count_text = f"\n\nEn aquest projecte s'han realitzat {num_tests} {assaig_word} DPSH."
            return base_text + count_text

        return base_text

    def generate_sondeig_description(self) -> str | None:
        """
        Generate sondeig description (conditional).

        Returns:
            Sondeig description if present, None otherwise
        """
        if not self.data.has_sondeig:
            return None
        return self.SONDEIG_DESCRIPTION

    def generate_spt_description(self) -> str | None:
        """
        Generate SPT description (conditional).

        Returns:
            SPT description if present, None otherwise
        """
        if not self.data.has_spt:
            return None
        return self.SPT_DESCRIPTION

    def generate_taula3_dpsh(self) -> list[dict[str, str]]:
        """
        Generate DPSH summary table (Taula 3).

        Returns:
            List of dictionaries with DPSH test data for table rendering

        Note:
            UTM coordinates are shown as "Vegeu planol" because the DPSHTest
            data model does not store per-test coordinates. The actual coordinates
            for each test point should be referenced from the site plan (planol).
        """
        rows = []

        if not self.data.dpsh or not self.data.dpsh.tests:
            return rows

        for test in self.data.dpsh.tests:
            # Format water level
            if test.water_detected and test.water_depth is not None:
                nf_value = f"{abs(test.water_depth):.2f}"
            else:
                nf_value = "-"

            # Format observations
            observations = []
            if test.refusal_reached:
                observations.append("Rebuig")
            obs_text = ", ".join(observations) if observations else "-"

            # Note: Per-test UTM coordinates not available in DPSHTest model.
            # Reference site plan for individual test locations.
            rows.append({
                'Assaig': test.test_id,
                'UTM X': "Vegeu planol",
                'UTM Y': "Vegeu planol",
                'Profunditat (m)': f"{test.depth_reached:.2f}",
                'NF (m)': nf_value,
                'Observacions': obs_text,
            })

        return rows

    def generate_taula4_sondeig(self) -> list[dict[str, str]] | None:
        """
        Generate Sondeig summary table (Taula 4) - conditional.

        Returns:
            List of dictionaries with sondeig data, or None if no sondeig
        """
        if not self.data.has_sondeig:
            return None

        # Use real data from sondeig_extracted.json if available
        if self.data.sondeig_tests:
            rows = []
            for test in self.data.sondeig_tests:
                test_id = test.get('test_id', 'S-?')
                total_depth = test.get('total_depth_m', 0)
                cota = self.data.cota_referencia or self.FALLBACK_VALUE

                # Format water level
                if test.get('water_detected') and test.get('water_level_m') is not None:
                    water = f"{abs(test['water_level_m']):.2f}"
                else:
                    water = "No detectat"

                # SPT/MA count: "n_spt/n_ma" (e.g. "1/--", "2/1")
                spt_results = test.get('spt_results', [])
                ma_results = test.get('ma_results', [])
                n_spt = len(spt_results)
                n_ma = len(ma_results)
                spt_ma = f"{n_spt}/{n_ma if n_ma else '--'}"

                rows.append({
                    'test_id': test_id,
                    'cota': cota,
                    'depth': f"-{total_depth:.2f}" if total_depth else self.FALLBACK_VALUE,
                    'spt_ma': spt_ma,
                    'water': water,
                })
            return rows

        # Fallback: minimal row from flags only
        return [{
            'test_id': 'S-1',
            'cota': self.data.cota_referencia or self.FALLBACK_VALUE,
            'depth': self.FALLBACK_VALUE,
            'spt_ma': self.FALLBACK_VALUE,
            'water': self.FALLBACK_VALUE,
        }]

    def generate_taula5_spt(self) -> list[dict[str, str]] | None:
        """
        Generate SPT summary table (Taula 5) - conditional.

        Returns:
            List of dictionaries with SPT data, or None if no SPT
        """
        if not self.data.has_spt:
            return None

        # Use spt_data from user_data.json
        spt = self.data.spt_data
        if spt and isinstance(spt, dict):
            return [{
                'Sondeig': spt.get('test_id', 'S-1'),
                'Profunditat (m)': spt.get('depth_range', '-'),
                'N30': str(spt.get('n30', '-')),
                'Observacions': spt.get('lithology', '-'),
            }]

        # If spt_data is a list (multiple SPT tests)
        if spt and isinstance(spt, list):
            return [{
                'Sondeig': item.get('test_id', 'S-1'),
                'Profunditat (m)': item.get('depth_range', '-'),
                'N30': str(item.get('n30', '-')),
                'Observacions': item.get('lithology', '-'),
            } for item in spt]

        # Fallback: SPT detected but no structured data
        return [{
            'Sondeig': 'S-1',
            'Profunditat (m)': '-',
            'N30': '-',
            'Observacions': '-',
        }]

    # === 2.5 ASSAIGS LABORATORI ===

    def generate_lab_intro(self) -> str:
        """
        Generate lab tests introduction.

        Returns:
            Static lab tests intro text
        """
        return self.LAB_INTRO

    def generate_taula6_lab(self) -> list[dict[str, str]]:
        """
        Generate lab tests table (Taula 6).

        Returns:
            List of dictionaries with lab test data
        """
        # Standard lab tests for this type of project
        rows = []

        # Add sulfate test if data available
        if self.data.sulfate_mg_kg is not None:
            rows.append({
                'Assaig': 'Contingut de sulfats solubles',
                'Norma': 'UNE 83963',
                'Resultat': f"{self.data.sulfate_mg_kg:.0f} mg/kg",
                'Observacions': self.data.aggressivity_class or "-",
            })

        # Placeholder for other standard tests
        if not rows:
            rows.append({
                'Assaig': '[Tipus d\'assaig]',
                'Norma': '[Norma UNE]',
                'Resultat': '[Resultat]',
                'Observacions': '-',
            })

        return rows

    # === Generate All ===

    def generate_all(self) -> Section2Content:
        """
        Generate all Section 2 content.

        Returns:
            Section2Content dataclass with all generated content
        """
        return Section2Content(
            # 2.1 DESCRIPCIO ZONA
            visit_date_paragraph=self.generate_visit_date_paragraph(),
            visit_objectives=self.generate_visit_objectives(),
            adjacent_parcels_paragraph=self.generate_adjacent_parcels(),
            site_description_paragraph=self.generate_site_description(),
            photo_references=self.get_photo_references(),
            # 2.2 RECONEIXEMENT DEL TERRENY
            test_dates_paragraph=self.generate_test_dates_paragraph(),
            test_list=self.generate_test_list(),
            lab_accreditation=self.generate_lab_accreditation(),
            # 2.3 JUSTIFICACIO CTE
            cte_justification=self.generate_cte_justification(),
            # 2.4 ASSAIGS IN SITU
            dpsh_description=self.generate_dpsh_description(),
            sondeig_description=self.generate_sondeig_description(),
            spt_description=self.generate_spt_description(),
            taula3_dpsh=self.generate_taula3_dpsh(),
            taula4_sondeig=self.generate_taula4_sondeig(),
            taula5_spt=self.generate_taula5_spt(),
            # 2.5 ASSAIGS LABORATORI
            lab_intro=self.generate_lab_intro(),
            taula6_lab=self.generate_taula6_lab(),
        )


# CLI for testing
if __name__ == '__main__':
    from pathlib import Path
    from datetime import date
    from dataclasses import dataclass, field as dataclass_field

    # Minimal data classes for standalone testing
    @dataclass
    class ClientData:
        company_name: str
        contact_name: str | None = None
        nif: str | None = None
        address: str | None = None

    @dataclass
    class DPSHReading:
        depth_m: float
        n20: int
        nb: float
        torque: float | None = None
        water_level: bool = False
        soil_level: str | None = None

    @dataclass
    class DPSHTest:
        test_id: str
        readings: list = dataclass_field(default_factory=list)
        correction_factor: float = 0.83

        @property
        def max_depth(self) -> float:
            if not self.readings:
                return 0.0
            return min(r.depth_m for r in self.readings)

        @property
        def depth_reached(self) -> float:
            return abs(self.max_depth)

        @property
        def refusal_reached(self) -> bool:
            return any(r.n20 >= 100 for r in self.readings)

        @property
        def water_detected(self) -> bool:
            return any(r.water_level for r in self.readings)

        @property
        def water_depth(self) -> float | None:
            for r in self.readings:
                if r.water_level:
                    return r.depth_m
            return None

    @dataclass
    class DPSHData:
        expedient: str
        tests: list = dataclass_field(default_factory=list)
        source_file: str = ""

        @property
        def num_tests(self) -> int:
            return len(self.tests)

    @dataclass
    class ReportData:
        expedient: str
        municipality: str
        report_date: date
        client: ClientData
        architect_name: str = ""
        architect_company: str = ""
        building_type: str = ""
        num_floors: str = ""
        superficie_parcela: float = 0.0
        superficie_construida: float = 0.0
        has_basement: bool = False
        has_retaining_walls: bool = False
        street_address: str = ""
        utm_x: float | None = None
        utm_y: float | None = None
        adjacent_parcels: dict = dataclass_field(default_factory=dict)
        site_position: str = "centre"
        parcel_shape: str = "rectangular"
        is_urban: bool = True
        is_sloped: bool = False
        dpsh: DPSHData | None = None
        has_sondeig: bool = False
        has_spt: bool = False
        sulfate_mg_kg: float | None = None
        aggressivity_class: str = ""

        @property
        def num_dpsh_tests(self) -> int:
            return self.dpsh.num_tests if self.dpsh else 0

    print("=" * 60)
    print("G3DT Section 2 Generator - Test")
    print("=" * 60)

    # Create test DPSH data
    readings = [
        DPSHReading(depth_m=-0.2, n20=5, nb=6.0),
        DPSHReading(depth_m=-0.4, n20=8, nb=9.6),
        DPSHReading(depth_m=-0.6, n20=12, nb=14.4),
        DPSHReading(depth_m=-0.8, n20=15, nb=18.0),
        DPSHReading(depth_m=-1.0, n20=18, nb=21.6),
        DPSHReading(depth_m=-1.2, n20=22, nb=26.4),
        DPSHReading(depth_m=-1.4, n20=28, nb=33.6),
        DPSHReading(depth_m=-1.6, n20=35, nb=42.0),
        DPSHReading(depth_m=-1.8, n20=100, nb=120.0),  # Refusal
    ]
    test1 = DPSHTest(test_id="P-1", readings=readings)
    test2 = DPSHTest(test_id="P-2", readings=readings[:6])  # Shorter test

    dpsh_data = DPSHData(
        expedient="4001612",
        tests=[test1, test2],
        source_file="DPSH.xls",
    )

    # Create test report data
    client = ClientData(
        company_name="Construccions Exemple SL",
        contact_name="Pere Garcia",
    )

    test_data = ReportData(
        expedient="4001612",
        municipality="Bell-lloc d'Urgell",
        report_date=date.today(),
        client=client,
        utm_x=307500.0,
        utm_y=4610200.0,
        adjacent_parcels={
            'north': "parcel·la veina amb habitatge",
            'south': "carrer Major",
            'east': "parcel·la buida",
            'west': "camp de conreu",
        },
        site_position="sud-est",
        parcel_shape="rectangular",
        is_urban=True,
        is_sloped=False,
        dpsh=dpsh_data,
        has_sondeig=False,
        has_spt=False,
        sulfate_mg_kg=850.0,
        aggressivity_class="Qa (Debilment agressiu)",
    )

    # Generate content
    generator = Section2Generator(test_data)
    content = generator.generate_all()

    # Display results
    print("\n" + "-" * 60)
    print("2.1 DESCRIPCIO ZONA")
    print("-" * 60)

    print("\n[Visit Date Paragraph]")
    print(content.visit_date_paragraph)

    print("\n[Visit Objectives]")
    print(content.visit_objectives)

    print("\n[Adjacent Parcels - 2.1.1]")
    print(content.adjacent_parcels_paragraph)

    print("\n[Site Description - 2.1.2]")
    print(content.site_description_paragraph)

    print("\n[Photo References]")
    for photo in content.photo_references:
        print(f"  - {photo}")

    print("\n" + "-" * 60)
    print("2.2 RECONEIXEMENT DEL TERRENY")
    print("-" * 60)

    print("\n[Test Dates]")
    print(content.test_dates_paragraph)

    print("\n[Test List]")
    for test in content.test_list:
        print(f"  - {test}")

    print("\n[Lab Accreditation]")
    print(content.lab_accreditation)

    print("\n" + "-" * 60)
    print("2.3 JUSTIFICACIO CTE")
    print("-" * 60)
    print(content.cte_justification)

    print("\n" + "-" * 60)
    print("2.4 ASSAIGS IN SITU")
    print("-" * 60)

    print("\n[DPSH Description - 2.4.1]")
    print(content.dpsh_description)

    print("\n[Sondeig Description - 2.4.2]")
    print(content.sondeig_description or "(No sondeig)")

    print("\n[SPT Description - 2.4.3]")
    print(content.spt_description or "(No SPT)")

    print("\n[Taula 3: DPSH Summary]")
    for row in content.taula3_dpsh:
        print(f"  {row}")

    print("\n[Taula 4: Sondeig Summary]")
    print(content.taula4_sondeig or "  (No sondeig)")

    print("\n[Taula 5: SPT Summary]")
    print(content.taula5_spt or "  (No SPT)")

    print("\n" + "-" * 60)
    print("2.5 ASSAIGS LABORATORI")
    print("-" * 60)

    print("\n[Lab Intro]")
    print(content.lab_intro)

    print("\n[Taula 6: Lab Tests]")
    for row in content.taula6_lab:
        print(f"  {row}")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
