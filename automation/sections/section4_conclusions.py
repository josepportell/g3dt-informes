#!/usr/bin/env python3
"""
G3DT Section 4 Generator: CONCLUSIONS

Generates content for the conclusions section of geotechnical reports.
Section 4 contains:
  4.1 GEOLOGIA - Soil levels summary and geotechnical parameters table
  4.2 HIDROGEOLOGIA I AGRESSIVITAT - Water level and aggressivity statements
  4.3 FONAMENTACIO - Bearing capacity and settlement recommendations
  4.4 EXPANSIVITAT (conditional) - Expansive soil assessment
  4.5 EMPENTES DE TERRES (conditional) - Earth pressure calculations
  4.6 ESTABILITAT VESSANT (conditional) - Slope stability assessment

Author: Eficients.cat
Date: 2026-02-03
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..report_data import ReportData


@dataclass
class GeotechParamsRow:
    """Single row of geotechnical parameters table (Taula 10)."""
    nivell: str
    descripcio: str
    gruix: str
    Nb: str  # Range of N20 values (e.g., "17-R")
    N: str   # Representative N value (e.g., "R" or "38")
    gamma: str
    cohesion: str
    phi: str
    E: str
    n20_mitja: str  # Kept for backwards compatibility


@dataclass
class Section4Content:
    """Generated content for Section 4."""
    # 4.1 GEOLOGIA
    geologia_summary: str
    figura6_reference: str
    taula10: list[GeotechParamsRow]

    # 4.2 HIDROGEOLOGIA I AGRESSIVITAT
    water_statement: str
    aggressivity_statement: str

    # 4.3 FONAMENTACIO
    excavation_paragraph: str
    qa_paragraph: str
    settlement_paragraph: str

    # 4.4 EXPANSIVITAT (conditional)
    expansivitat_paragraph: str | None = None

    # 4.5 EMPENTES DE TERRES (conditional)
    empentes_paragraph: str | None = None
    ka_value: float | None = None
    kp_value: float | None = None

    # 4.6 ESTABILITAT VESSANT (conditional)
    estabilitat_paragraph: str | None = None


class Section4Generator:
    """Generates Section 4: CONCLUSIONS."""

    # Static templates
    WATER_DETECTED_TEXT = (
        "Durant l'execució dels treballs de camp s'ha detectat presència "
        "de nivell freàtic a una fondària de {depth:.2f} m respecte la rasant actual del terreny."
    )
    WATER_NOT_DETECTED_TEXT = (
        "Durant l'execució dels treballs de camp no s'ha detectat presència "
        "de nivell freàtic dins la fondària investigada."
    )

    AGGRESSIVITY_TEXTS = {
        'Qa': "El terreny es classifica com a NO AGRESSIU al formigó segons la norma EHE-08.",
        'Qb': "El terreny presenta una agressivitat FEBLE al formigó segons la norma EHE-08. "
              "Es recomana l'ús de ciment tipus SR (sulforesistent).",
        'Qc': "El terreny presenta una agressivitat MITJANA al formigó segons la norma EHE-08. "
              "És obligatori l'ús de ciment tipus SR (sulforesistent).",
        '': "No s'han realitzat assaigs de contingut en sulfats.",
    }

    EXCAVATION_TEMPLATE = (
        "Considerant una excavació per a fonaments superficials fins a una fondària "
        "aproximada de {Df:.2f} m respecte la rasant actual, i un ample de sabata mínim de {B:.2f} m, "
        "es recomana adoptar els següents paràmetres de disseny:"
    )

    FALLBACK_VALUE = "-"

    def __init__(self, data: ReportData):
        """
        Initialize generator with report data.

        Args:
            data: ReportData instance with all project information
        """
        self.data = data

    def _safe_value(self, value: float | None, fmt: str = ".2f") -> str:
        """Return formatted value or fallback."""
        if value is not None:
            return f"{value:{fmt}}"
        return self.FALLBACK_VALUE

    def generate_geologia_summary(self) -> str:
        """
        Generate geology summary paragraph (4.1).

        Describes soil levels detected during investigation.
        """
        if not self.data.soil_levels:
            return "No s'han definit nivells geotècnics diferenciats."

        num_levels = len(self.data.soil_levels)

        if num_levels == 1:
            level = self.data.soil_levels[0]
            summary = (
                f"Segons els resultats dels assaigs de penetració realitzats, "
                f"s'ha identificat un únic nivell geotècnic fins a la fondària investigada. "
                f"Aquest nivell correspon a {level.description.lower()} "
                f"amb un valor mitjà de N20 de {level.n20_average:.0f} cops."
            )
            summary += self._icgc_unit_reference()
            return summary

        levels_text = []
        for level in self.data.soil_levels:
            thickness_text = (
                f"de {level.thickness_m:.2f} m de gruix"
                if level.thickness_m
                else "de gruix indeterminat"
            )
            levels_text.append(
                f"Nivell {level.level_number}: {level.description} ({thickness_text}, "
                f"N20 mitjà = {level.n20_average:.0f})"
            )

        summary = (
            f"Segons els resultats dels assaigs de penetració realitzats, "
            f"s'han identificat {num_levels} nivells geotècnics diferenciats:\n\n"
            + "\n".join(f"- {t}" for t in levels_text)
        )

        summary += self._icgc_unit_reference()
        return summary

    def _icgc_unit_reference(self) -> str:
        """Append ICGC geological unit reference if available."""
        if not self.data.icgc_unit_code:
            return ""
        unit_ref = "Aquest nivell s'ha identificat com materials"
        if self.data.icgc_unit_epoch:
            unit_ref += f" d'edat {self.data.icgc_unit_epoch}"
        unit_ref += f", unitat cartogràfica {self.data.icgc_unit_code}"
        if self.data.icgc_unit_description:
            unit_ref += f" ({self.data.icgc_unit_description})"
        unit_ref += " del mapa geològic 1:25.000 de l'ICGC."
        return f"\n\n{unit_ref}"

    def generate_figura6_reference(self) -> str:
        """Generate reference to Figure 6 (cross-section)."""
        return "[FIGURA 6: Tall geologic esquematic]"

    def generate_taula10(self) -> list[GeotechParamsRow]:
        """
        Generate Table 10: Geotechnical parameters table.

        Returns:
            List of GeotechParamsRow for each soil level

        Note:
            Currently only supports single-level soils. Multi-level soils would
            require per-level geotechnical parameters (gamma, cohesion, phi, E)
            rather than a single shared GeotechnicalParams instance.
        """
        if not self.data.soil_levels:
            return []

        rows = []
        params = self.data.geotechnical_params

        for level in self.data.soil_levels:
            thickness_text = (
                f">{level.thickness_m:.2f}" if level.thickness_m else ">investigat"
            )

            # Compute Nb (range) and N (representative) from n20_min/n20_max
            nb, n = self._compute_nb_n(level)

            if params:
                rows.append(GeotechParamsRow(
                    nivell=f"{level.level_number}r Nivell",
                    descripcio=level.description,
                    gruix=thickness_text,
                    Nb=nb,
                    N=n,
                    gamma=f"{params.gamma:.2f}",
                    cohesion=f"{params.cohesion:.2f}",
                    phi=f"{params.phi:.0f}",
                    E=f"{params.E:.0f}",
                    n20_mitja=f"{level.n20_average:.0f}",
                ))
            else:
                rows.append(GeotechParamsRow(
                    nivell=f"{level.level_number}r Nivell",
                    descripcio=level.description,
                    gruix=thickness_text,
                    Nb=nb,
                    N=n,
                    gamma=self.FALLBACK_VALUE,
                    cohesion=self.FALLBACK_VALUE,
                    phi=self.FALLBACK_VALUE,
                    E=self.FALLBACK_VALUE,
                    n20_mitja=f"{level.n20_average:.0f}",
                ))

        return rows

    def _compute_nb_n(self, level) -> tuple[str, str]:
        """
        Compute Nb (range) and N (representative) values for a soil level.

        Nb: "min-max" range where 100+ = "R" (refusal)
        N: representative value; "R" if any reading hit refusal, else average

        User overrides from geomech_params.Nb / geomech_params.N take precedence.
        """
        # Check for user overrides
        if hasattr(self.data, '_geomech_overrides'):
            overrides = self.data._geomech_overrides
        else:
            overrides = {}
        nb_override = overrides.get('Nb', '')
        n_override = overrides.get('N', '')
        if nb_override and n_override:
            return nb_override, n_override

        # Compute from level data
        nb_min = level.n20_min if level.n20_min is not None else level.n20_average
        nb_max = level.n20_max if level.n20_max is not None else level.n20_average
        nb_min_str = f"{nb_min:.0f}" if nb_min < 100 else "R"
        nb_max_str = "R" if nb_max >= 100 else f"{nb_max:.0f}"
        nb = nb_override if nb_override else f"{nb_min_str}-{nb_max_str}"

        n = n_override if n_override else (
            "R" if (level.n20_max is not None and level.n20_max >= 100)
            else f"{level.n20_average:.0f}"
        )

        return nb, n

    def generate_water_statement(self) -> str:
        """
        Generate water level statement (4.2).

        Uses conditional template based on water detection.
        """
        if self.data.water_detected:
            depth = self._get_water_depth()
            if depth is not None:
                return self.WATER_DETECTED_TEXT.format(depth=depth)
            return (
                "Durant l'execució dels treballs de camp s'ha detectat presència "
                "de nivell freàtic (fondària no determinada amb precisió)."
            )
        return self.WATER_NOT_DETECTED_TEXT

    def _get_water_depth(self) -> float | None:
        """Get water depth from DPSH data if available."""
        if not self.data.dpsh or not self.data.dpsh.tests:
            return None

        for test in self.data.dpsh.tests:
            for reading in test.readings:
                if reading.water_level:
                    return abs(reading.depth_m)
        return None

    def generate_aggressivity_statement(self) -> str:
        """
        Generate aggressivity statement (4.2).

        Classifies based on sulfate content according to EHE-08.
        """
        if self.data.aggressivity_class:
            return self.AGGRESSIVITY_TEXTS.get(
                self.data.aggressivity_class,
                self.AGGRESSIVITY_TEXTS['']
            )

        if self.data.sulfate_mg_kg is not None:
            agg_class = self._classify_aggressivity(self.data.sulfate_mg_kg)
            return (
                f"El contingut en sulfats del terreny es de {self.data.sulfate_mg_kg:.0f} mg/kg. "
                + self.AGGRESSIVITY_TEXTS.get(agg_class, self.AGGRESSIVITY_TEXTS[''])
            )

        return self.AGGRESSIVITY_TEXTS['']

    @staticmethod
    def _classify_aggressivity(sulfate_mg_kg: float) -> str:
        """
        Classify aggressivity based on sulfate content (EHE-08).

        Thresholds:
        - Qa (non-aggressive): < 2000 mg/kg
        - Qb (weak): 2000-3000 mg/kg
        - Qc (medium): 3000-12000 mg/kg
        """
        if sulfate_mg_kg < 2000:
            return 'Qa'
        if sulfate_mg_kg < 3000:
            return 'Qb'
        return 'Qc'

    def generate_excavation_paragraph(self) -> str:
        """
        Generate excavation context paragraph (4.3).

        Uses Terzaghi result parameters if available.
        """
        if self.data.terzaghi_result:
            return self.EXCAVATION_TEMPLATE.format(
                Df=self.data.terzaghi_result.Df,
                B=self.data.terzaghi_result.B,
            )

        return (
            "Considerant una excavació per a fonaments superficials, "
            "es recomana adoptar els següents paràmetres de disseny:"
        )

    def generate_qa_paragraph(self) -> str:
        """
        Generate bearing capacity recommendation paragraph (4.3).

        Uses Terzaghi result's format_for_report() method.
        """
        if self.data.terzaghi_result:
            return self.data.terzaghi_result.format_for_report()

        if self.data.qa_value:
            return f"Qa= {self.data.qa_value:.1f} Kg/cm2 amb un factor de seguretat inclòs de F=3"

        return "[Capacitat portant no calculada]"

    def generate_settlement_paragraph(self) -> str:
        """
        Generate settlement estimate paragraph (4.3).

        Uses Terzaghi result's format_settlement_for_report() method.
        """
        if self.data.terzaghi_result:
            settlement_text = self.data.terzaghi_result.format_settlement_for_report()
            if settlement_text:
                return settlement_text

        return (
            "Els assentaments maxims previstos per la carrega recomanada "
            "anteriorment seran admissibles segons la normativa vigent."
        )

    def generate_expansivitat(self) -> str | None:
        """
        Generate expansivity section (4.4) if applicable.

        Only generated when include_expansivity is True.
        """
        if not self.data.include_expansivity:
            return None

        return (
            "Segons les característiques del terreny observades, "
            "es recomana considerar el potencial expansiu del sòl. "
            "Es suggereix realitzar assaigs d'expansivitat (Lambe) "
            "per determinar la pressió d'inflament i adoptar les mesures "
            "constructives adequades en cas necessari."
        )

    def generate_empentes(self) -> tuple[str | None, float | None, float | None]:
        """
        Generate earth pressure section (4.5) if applicable.

        Calculates Ka (active) and Kp (passive) coefficients.

        Returns:
            Tuple of (paragraph, Ka, Kp) or (None, None, None) if not applicable
        """
        if not self.data.include_earth_pressure:
            return None, None, None

        if not self.data.geotechnical_params:
            return (
                "Es recomana el càlcul de les empentes de terres per al disseny "
                "dels murs de contenció segons la normativa vigent.",
                None,
                None
            )

        phi_rad = self.data.geotechnical_params.phi * math.pi / 180
        ka = (1 - math.sin(phi_rad)) / (1 + math.sin(phi_rad))
        kp = (1 + math.sin(phi_rad)) / (1 - math.sin(phi_rad))

        paragraph = (
            f"Per al disseny dels murs de contenció, s'han calculat els "
            f"coeficients d'empenta de Rankine:\n\n"
            f"- Coeficient d'empenta activa: Ka = {ka:.3f}\n"
            f"- Coeficient d'empenta passiva: Kp = {kp:.3f}\n\n"
            f"Amb un angle de fricció interna de {self.data.geotechnical_params.phi:.0f} "
            f"i una densitat de {self.data.geotechnical_params.gamma:.2f} g/cm3."
        )

        return paragraph, ka, kp

    def generate_estabilitat(self) -> str | None:
        """
        Generate slope stability section (4.6) if applicable.

        This is a complex calculation (Hoek & Bray) and may require deferral
        to manual analysis for non-standard cases.
        """
        if not self.data.include_slope_stability:
            return None

        return (
            "Donada la presència de vessant a la zona del projecte, "
            "es recomana realitzar un estudi específic d'estabilitat "
            "de talussos segons el mètode de Hoek & Bray o equivalent. "
            "S'haurà de considerar l'angle del vessant natural, "
            "les característiques resistents del terreny i les "
            "condicions hidrològiques de la zona."
        )

    def generate_all(self) -> Section4Content:
        """
        Generate all Section 4 content.

        Returns:
            Section4Content dataclass with all generated content
        """
        empentes_para, ka, kp = self.generate_empentes()

        return Section4Content(
            geologia_summary=self.generate_geologia_summary(),
            figura6_reference=self.generate_figura6_reference(),
            taula10=self.generate_taula10(),
            water_statement=self.generate_water_statement(),
            aggressivity_statement=self.generate_aggressivity_statement(),
            excavation_paragraph=self.generate_excavation_paragraph(),
            qa_paragraph=self.generate_qa_paragraph(),
            settlement_paragraph=self.generate_settlement_paragraph(),
            expansivitat_paragraph=self.generate_expansivitat(),
            empentes_paragraph=empentes_para,
            ka_value=ka,
            kp_value=kp,
            estabilitat_paragraph=self.generate_estabilitat(),
        )


# CLI for testing
if __name__ == '__main__':
    from dataclasses import dataclass as dc
    from datetime import date

    # Minimal data classes for standalone testing
    @dc
    class ClientData:
        company_name: str
        contact_name: str | None = None
        nif: str | None = None
        address: str | None = None

    @dc
    class SoilLevel:
        level_number: int
        description: str
        thickness_m: float | None
        n20_average: float
        depth_from_m: float = 0.0
        depth_to_m: float | None = None
        n20_min: float | None = None
        n20_max: float | None = None

    @dc
    class GeotechnicalParams:
        gamma: float
        cohesion: float
        phi: float
        E: float

    @dc
    class BearingCapacityResult:
        phi: float
        cohesion: float
        gamma: float
        B: float
        Df: float
        Qa: float
        safety_factor: float = 3.0
        settlement_cm: float | None = None
        settlement_type: str = "immediat"

        def format_for_report(self) -> str:
            return f"Qa= {self.Qa:.1f} Kg/cm2 amb un factor de seguretat inclos de F={int(self.safety_factor)}"

        def format_settlement_for_report(self) -> str:
            if self.settlement_cm is None:
                return ""
            return (
                f"Els assentaments maxims previstos per la carrega recomanada "
                f"anteriorment seran inferiors a {self.settlement_cm:.2f} cm, "
                f"{self.settlement_type}s en el temps"
            )

    @dc
    class DPSHReading:
        depth_m: float
        n20: int
        nb: int
        water_level: bool = False

    @dc
    class DPSHTest:
        test_id: str
        readings: list

    @dc
    class DPSHData:
        expedient: str
        tests: list
        source_file: str = ""

        @property
        def overall_average_n20(self) -> float:
            total = 0
            count = 0
            for test in self.tests:
                for r in test.readings:
                    total += r.n20
                    count += 1
            return total / count if count > 0 else 0

        @property
        def any_water_detected(self) -> bool:
            for test in self.tests:
                for r in test.readings:
                    if r.water_level:
                        return True
            return False

    @dc
    class ReportData:
        expedient: str
        municipality: str
        report_date: date
        client: ClientData
        architect_name: str
        architect_company: str
        building_type: str
        num_floors: str
        superficie_parcela: float
        superficie_construida: float
        has_basement: bool
        has_retaining_walls: bool
        street_address: str
        dpsh: DPSHData | None = None
        soil_levels: list = None
        geotechnical_params: GeotechnicalParams | None = None
        terzaghi_result: BearingCapacityResult | None = None
        sulfate_mg_kg: float | None = None
        aggressivity_class: str = ""
        icgc_unit_code: str = ""
        icgc_unit_description: str = ""
        icgc_unit_epoch: str = ""
        _geomech_overrides: dict = None
        include_expansivity: bool = False
        include_earth_pressure: bool = False
        include_slope_stability: bool = False

        def __post_init__(self):
            if self.soil_levels is None:
                self.soil_levels = []
            if self._geomech_overrides is None:
                self._geomech_overrides = {}

        @property
        def water_detected(self) -> bool:
            return self.dpsh.any_water_detected if self.dpsh else False

        @property
        def qa_value(self) -> float | None:
            return self.terzaghi_result.Qa if self.terzaghi_result else None

    print("=" * 60)
    print("G3DT Section 4 Generator - Test")
    print("=" * 60)

    # Create test data
    client = ClientData(company_name="Construccions Test SL")

    soil_levels = [
        SoilLevel(
            level_number=1,
            description="Graves i sorres amb matriu llimosa",
            thickness_m=None,
            n20_average=36.0,
            n20_min=28.0,
            n20_max=42.0,
        )
    ]

    geotech_params = GeotechnicalParams(
        gamma=2.1,
        cohesion=0.0,
        phi=38.0,
        E=400.0,
    )

    terzaghi_result = BearingCapacityResult(
        phi=38.0,
        cohesion=0.0,
        gamma=2.1,
        B=1.0,
        Df=0.8,
        Qa=2.5,
        safety_factor=3.0,
        settlement_cm=0.85,
        settlement_type="immediat",
    )

    dpsh_readings = [
        DPSHReading(depth_m=-0.6, n20=28, nb=7),
        DPSHReading(depth_m=-1.2, n20=35, nb=9),
        DPSHReading(depth_m=-1.8, n20=42, nb=11),
    ]
    dpsh_test = DPSHTest(test_id="P-1", readings=dpsh_readings)
    dpsh_data = DPSHData(expedient="4001612", tests=[dpsh_test])

    test_data = ReportData(
        expedient="4001612",
        municipality="Bell-lloc d'Urgell",
        report_date=date.today(),
        client=client,
        architect_name="Joan Arquitecte",
        architect_company="Arquitectura SLP",
        building_type="Habitatge unifamiliar",
        num_floors="Pb + 1Pp",
        superficie_parcela=450.0,
        superficie_construida=220.0,
        has_basement=True,
        has_retaining_walls=True,
        street_address="Carrer Major, 1",
        dpsh=dpsh_data,
        soil_levels=soil_levels,
        geotechnical_params=geotech_params,
        terzaghi_result=terzaghi_result,
        sulfate_mg_kg=850.0,
        include_expansivity=False,
        include_earth_pressure=True,
        include_slope_stability=False,
    )

    # Generate content
    generator = Section4Generator(test_data)
    content = generator.generate_all()

    # Display results
    print("\n" + "-" * 60)
    print("4.1 GEOLOGIA")
    print("-" * 60)

    print("\n[Summary Paragraph]")
    print(content.geologia_summary)

    print("\n[Figura 6 Reference]")
    print(content.figura6_reference)

    print("\n[Taula 10: Parametres geotecnics]")
    if content.taula10:
        print("  Nivell | Descripcio | Gruix | Nb | N | gamma | c | phi | E | N20")
        print("  " + "-" * 70)
        for row in content.taula10:
            print(f"  {row.nivell} | {row.descripcio[:15]} | {row.gruix} | "
                  f"{row.Nb} | {row.N} | "
                  f"{row.gamma} | {row.cohesion} | {row.phi} | {row.E} | {row.n20_mitja}")

    print("\n" + "-" * 60)
    print("4.2 HIDROGEOLOGIA I AGRESSIVITAT")
    print("-" * 60)

    print("\n[Water Statement]")
    print(content.water_statement)

    print("\n[Aggressivity Statement]")
    print(content.aggressivity_statement)

    print("\n" + "-" * 60)
    print("4.3 FONAMENTACIO")
    print("-" * 60)

    print("\n[Excavation Paragraph]")
    print(content.excavation_paragraph)

    print("\n[Qa Paragraph]")
    print(content.qa_paragraph)

    print("\n[Settlement Paragraph]")
    print(content.settlement_paragraph)

    # Conditional sections
    if content.expansivitat_paragraph:
        print("\n" + "-" * 60)
        print("4.4 EXPANSIVITAT")
        print("-" * 60)
        print(content.expansivitat_paragraph)

    if content.empentes_paragraph:
        print("\n" + "-" * 60)
        print("4.5 EMPENTES DE TERRES")
        print("-" * 60)
        print(content.empentes_paragraph)
        print(f"\n  Ka = {content.ka_value:.3f}")
        print(f"  Kp = {content.kp_value:.3f}")

    if content.estabilitat_paragraph:
        print("\n" + "-" * 60)
        print("4.6 ESTABILITAT VESSANT")
        print("-" * 60)
        print(content.estabilitat_paragraph)

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
