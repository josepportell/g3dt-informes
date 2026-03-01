#!/usr/bin/env python3
"""
G3DT Section 3 Generator: DESCRIPCIO GEOLOGICA

Generates content for the geological description section of geotechnical reports.
Section 3 contains:
  3.1 MARC GEOLOGIC - Regional geology from ICGC API + regional templates
  3.2 MATERIALS - Soil level descriptions (PLACEHOLDER - needs zone templates)
  3.3 HIDROGEOLOGIA - Surface/groundwater hydrology
  3.4 AGRESSIVITAT - Sulfate classification (EHE-08)
  3.5 EXCAVABILITAT - Excavation difficulty assessment
  3.6 SISMICA - Seismic parameters (PLACEHOLDER - needs municipality lookup)
  3.7 RADO - Radon zone (PLACEHOLDER - needs municipality lookup)

Note: Section 3.1 now uses ICGC WMS API for authoritative geological data.
Other subsections still use placeholders pending zone templates.

Author: Eficients.cat
Date: 2026-02-03
Updated: 2026-02-04 - Added ICGC geology integration for section 3.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..icgc_geology import (
    get_geological_unit,
    determine_region,
    GeologicalUnit,
    ICGCError,
    ICGCConnectionError,
    ICGCCoordinateError,
    ICGCNoDataError,
)
from ..municipal_data import (
    get_seismic_ab_with_status,
    is_seismic_norm_required,
    get_radon_info_with_status,
    SeismicLookupResult,
    RadonInfoWithStatus,
)
from ..csn_radon import get_radon_potential_text

if TYPE_CHECKING:
    from ..report_data import ReportData

logger = logging.getLogger(__name__)


@dataclass
class PermeabilityRow:
    """Single row of permeability table (Taula 7)."""
    material: str
    permeabilitat: str
    k_m_s: str


@dataclass
class Section3Content:
    """Generated content for Section 3."""
    # 3.1 MARC GEOLOGIC
    marc_geologic: str  # Placeholder - needs zone templates
    figura4_reference: str

    # 3.2 MATERIALS
    materials_intro: str
    materials_levels: list[str]  # Placeholders for level descriptions
    sample_photos: list[str]

    # 3.3 HIDROGEOLOGIA
    hidrogeologia_surface: str
    hidrogeologia_groundwater: str
    taula7_permeability: list[PermeabilityRow]

    # 3.4 AGRESSIVITAT
    agressivitat: str

    # 3.5 EXCAVABILITAT
    excavabilitat: str

    # 3.6 SISMICA
    sismica: str  # Partial placeholder for ab parameter

    # 3.7 RADO
    rado: str  # Placeholder for zone lookup

    # Per-level generated texts (for template loop)
    depth_texts: list[str] = field(default_factory=list)  # Per-level depth/location descriptions
    geomech_texts: list[str] = field(default_factory=list)  # Per-level geomechanical descriptions


class Section3Generator:
    """Generates Section 3: DESCRIPCIO GEOLOGICA."""

    # === 3.1 MARC GEOLOGIC - Templates ===
    # Regional templates directory (relative to this file)
    TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "geological_regions"

    # Common instruction suffix for fallback/incomplete texts
    _MANUAL_INSTRUCTION_SUFFIX = (
        "Si us plau, introduïu manualment el text de marc geològic o "
        "verifiqueu les coordenades UTM del projecte."
    )

    # Fallback placeholder when ICGC/templates unavailable
    MARC_GEOLOGIC_PLACEHOLDER = (
        "[PENDENT: Text de marc geologic regional]\n\n"
        "No s'ha pogut obtenir la informació geològica de l'ICGC. "
        "Contacteu amb l'administrador o introduïu el text manualment."
    )

    # Regional template content (loaded from files)
    # Format: region_name -> list of paragraphs
    REGIONAL_TEMPLATES: dict[str, list[str]] = {
        'depressio_ebre': [
            # Paragraph 1: Regional context
            (
                "La zona que avarca aquest estudi es troba situada dins la Depressió de l'Ebre, "
                "en el seu extrem oriental, que rep el nom de Depressió Central Catalana. "
                "Aquesta és una unitat morfoestructural que forma part d'una conca sedimentària "
                "d'avantpaís desenvolupada entre la fi del Cretaci superior i el Miocè Superior."
            ),
            # Paragraph 2: Tectonic evolution
            (
                "La conca de l'Ebre està relacionada amb l'evolució de l'orogen pirinenc, "
                "i es desenvolupa com a resposta de l'apropament de la placa Ibèrica sota "
                "la placa Euroasiàtica, amb inici de subducció de la primera respecte la segona. "
                "D'aquesta manera, aquesta conca és una fossa tectònica formada entre els Pirineus, "
                "al nord, i les Serralades Costaneres Catalanes, al sud-est."
            ),
            # Paragraph 3: Eocene conditions
            (
                "Durant l'Eocè, la conca de l'Ebre estava connectada amb l'oceà Atlàntic per l'oest. "
                "Fruit de la col·lisió entre les dues plaques tectòniques, s'inicia la col·locació "
                "de làmines encavalcants o mantells de corriment que van avançant, progressivament, "
                "cap al sud en el cas del Pirineu i cap al nord en el cas de les Serralades "
                "Costaneres Catalanes."
            ),
            # Paragraph 4: Oligocene sedimentation
            (
                "A partir de finals de l'Eocè i durant tot l'Oligocè, la conca de l'Ebre actua "
                "com a conca endorreica, tancada, on la sedimentació que es produeix és d'origen "
                "continental. Els sediments continentals terciaris es troben organitzats en fàcies "
                "clàstiques al·luvials a prop de les serralades emergides (conglomerats i gresos), "
                "que passen a fàcies lacustres (margues, guixos i calcàries) cap a les zones "
                "centrals de la conca."
            ),
            # Paragraph 5: Present erosion
            (
                "Des de finals de l'Oligocè fins a l'actualitat la depressió de l'Ebre ha deixat "
                "d'actuar com a conca sedimentària i ha esdevingut una cubeta on l'agent predominant "
                "principal ha estat l'erosió. Localment, durant el Quaternari s'han dipositat "
                "materials sedimentaris recents en forma de terrasses fluvials, cons al·luvials "
                "i glacis associats als cursos fluvials actuals i a la dinàmica dels vessants."
            ),
        ],
        'valles_penedes': [
            # Paragraph 1: Regional context
            (
                "La zona que avarca aquest estudi es troba situada dins la Depressió Prelitoral "
                "Catalana, concretament a la fossa tectònica del Vallès-Penedès. Aquesta és una "
                "estructura d'origen extensional que forma part del sistema de fosses neògenes "
                "que caracteritzen el marge oriental de la Península Ibèrica, desenvolupada "
                "principalment durant el Miocè."
            ),
            # Paragraph 2: Tectonic evolution
            (
                "La fossa del Vallès-Penedès està relacionada amb l'obertura de la Mediterrània "
                "occidental i la formació del solc de València durant el Neogen. Es desenvolupa "
                "com a resposta a l'extensió crustal que va afectar el marge ibèric, generant "
                "un sistema de falles normals que van delimitar aquesta depressió entre la "
                "Serralada Prelitoral, al nord-oest, i la Serralada Litoral, al sud-est."
            ),
            # Paragraph 3: Miocene sedimentation
            (
                "Durant el Miocè, la fossa del Vallès-Penedès va actuar com a conca sedimentària, "
                "alternant períodes de sedimentació marina i continental. Els sediments miocens "
                "inclouen fàcies marines (margues, calcàries i gresos) corresponents a les "
                "transgressions mediterrànies, i fàcies continentals al·luvials i lacustres "
                "als marges de la conca."
            ),
            # Paragraph 4: Quaternary infill
            (
                "A partir del Pliocè i durant el Quaternari, la conca ha estat reblerta "
                "progressivament per sediments continentals. Els materials quaternaris inclouen "
                "dipòsits al·luvials, cons de dejecció procedents de les serralades adjacents, "
                "i terrasses fluvials associades als cursos d'aigua principals com el Llobregat "
                "i els seus afluents."
            ),
            # Paragraph 5: Present configuration
            (
                "En l'actualitat, la Depressió del Vallès-Penedès presenta una morfologia plana "
                "o suaument ondulada, amb relleus residuals formats per materials més resistents. "
                "Els processos actius inclouen la sedimentació al·luvial als fons de vall i "
                "l'erosió als vessants de les serralades que l'emmarquen. La zona urbanitzada "
                "se situa predominantment sobre els dipòsits quaternaris més recents."
            ),
        ],
    }

    # === 3.2 MATERIALS - Templates ===
    MATERIALS_INTRO_TEMPLATE = (
        "A partir dels resultats dels assaigs de penetracio dinamica realitzats, "
        "s'han identificat {num_levels} {nivell_word} geotecnic{plural} fins a la "
        "fondaria investigada."
    )

    MATERIALS_LEVEL_PLACEHOLDER = (
        "[PENDENT: Descripcio del nivell {level_num}]\n\n"
        "Requereix plantilla de zona per a descriure la litologia, "
        "color, consistencia i caracteristiques del material."
    )

    # N20 classification thresholds for geomechanical characterization
    N20_THRESHOLDS = {
        # (min, max): (consistency_cat, bearing_cat, granular_desc)
        (0, 5): ('molt fluixa', 'baixa', 'solts'),
        (5, 10): ('fluixa', 'baixa a mitja', 'poc compactes'),
        (10, 20): ('mitja', 'mitja', 'mitjanament compactes'),
        (20, 35): ('compacta', 'mitja a elevada', 'compactes'),
        (35, 50): ('molt compacta', 'elevada', 'molt compactes'),
        (50, 1000): ('densa', 'molt elevada', 'molt densos'),
    }

    # Regional material templates
    MATERIALS_TEMPLATES = {
        'depressio_ebre': {
            'granular': {
                'colors': 'coloracions clars a marró clar',
                'characteristics': (
                    'Aquests materials presenten característiques carbonatades '
                    'típiques de la Depressió de l\'Ebre.'
                ),
                'template': (
                    'El nivell {level_num} està format per {lithology}, de {colors}. '
                    '{characteristics} {surface_note}\n\n'
                    'Aquest nivell s\'ha identificat com a materials {epoch}, '
                    'unitat {icgc_code} segons l\'ICGC.\n\n'
                    'A partir dels assaigs realitzats, aquest nivell es detecta {depth_range}. '
                    'Aquests materials presenten un valor mitjà de N20 de {n20_avg:.0f} cops.\n\n'
                    'Des del punt de vista geomecànic es tracta d\'uns materials de caràcter '
                    'generalment granulars, amb una densitat i una capacitat portant {bearing}. '
                    'Dels assaigs de penetració dinàmica es dedueix una consistència {consistency}.'
                ),
            },
            'cohesiu': {
                'colors': 'coloracions marrons a grisenques',
                'characteristics': (
                    'Aquests materials presenten una plasticitat variable i són '
                    'típics dels dipòsits de la Depressió de l\'Ebre.'
                ),
                'template': (
                    'El nivell {level_num} està format per {lithology}, de {colors}. '
                    '{characteristics} {surface_note}\n\n'
                    'Aquest nivell s\'ha identificat com a materials {epoch}, '
                    'unitat {icgc_code} segons l\'ICGC.\n\n'
                    'A partir dels assaigs realitzats, aquest nivell es detecta {depth_range}. '
                    'Aquests materials presenten un valor mitjà de N20 de {n20_avg:.0f} cops.\n\n'
                    'Des del punt de vista geomecànic es tracta d\'uns materials de caràcter '
                    'cohesiu, amb una consistència {consistency} i una capacitat portant {bearing}.'
                ),
            },
        },
        'valles_penedes': {
            'granular': {
                'colors': 'coloracions marrons a vermelloses',
                'characteristics': (
                    'Aquests materials presenten una composició silícia típica dels '
                    'dipòsits del Vallès-Penedès, amb components procedents de l\'erosió '
                    'de les serralades adjacents.'
                ),
                'template': (
                    'El nivell {level_num} està format per {lithology}, de {colors}. '
                    '{characteristics} {surface_note}\n\n'
                    'Aquest nivell s\'ha identificat com a materials {epoch}, '
                    'unitat {icgc_code} segons l\'ICGC.\n\n'
                    'A partir dels assaigs realitzats, aquest nivell es detecta {depth_range}. '
                    'Aquests materials presenten un valor mitjà de N20 de {n20_avg:.0f} cops.\n\n'
                    'Des del punt de vista geomecànic es tracta d\'uns materials de caràcter '
                    'generalment granulars, amb una densitat i una capacitat portant {bearing}. '
                    'Dels assaigs de penetració dinàmica es dedueix una consistència {consistency}.'
                ),
            },
            'cohesiu': {
                'colors': 'coloracions marrons a grisenques',
                'characteristics': (
                    'Aquests materials presenten una plasticitat variable i són '
                    'típics dels dipòsits de la fossa del Vallès-Penedès.'
                ),
                'template': (
                    'El nivell {level_num} està format per {lithology}, de {colors}. '
                    '{characteristics} {surface_note}\n\n'
                    'Aquest nivell s\'ha identificat com a materials {epoch}, '
                    'unitat {icgc_code} segons l\'ICGC.\n\n'
                    'A partir dels assaigs realitzats, aquest nivell es detecta {depth_range}. '
                    'Aquests materials presenten un valor mitjà de N20 de {n20_avg:.0f} cops.\n\n'
                    'Des del punt de vista geomecànic es tracta d\'uns materials de caràcter '
                    'cohesiu, amb una consistència {consistency} i una capacitat portant {bearing}.'
                ),
            },
        },
    }

    # === 3.3 HIDROGEOLOGIA - Templates ===
    HIDROGEOLOGIA_SURFACE_URBAN = (
        "La parcel.la es troba en zona urbana consolidada, amb un sistema "
        "de drenatge municipal que recull les aigues superficials. "
        "No s'observen cursos d'aigua naturals ni zones d'acumulacio "
        "d'aigua a les proximitats immediates."
    )

    HIDROGEOLOGIA_SURFACE_RURAL = (
        "La parcel.la es troba en zona rural o periurbana. "
        "Les aigues superficials drenen de forma natural seguint "
        "la topografia del terreny. S'ha de considerar la possible "
        "presencia de cursos d'aigua estacionals a les proximitats."
    )

    HIDROGEOLOGIA_WATER_DETECTED = (
        "Durant l'execucio dels treballs de camp s'ha detectat presencia "
        "de nivell freatic a una fondaria de {depth:.2f} m respecte la rasant actual. "
        "Es recomana tenir en compte aquest nivell per al disseny de la fonamentacio "
        "i l'execucio de l'excavacio."
    )

    HIDROGEOLOGIA_WATER_NOT_DETECTED = (
        "Durant l'execucio dels treballs de camp no s'ha detectat presencia "
        "de nivell freatic dins la fondaria investigada. No obstant aixo, "
        "es recomana preveure possibles oscil.lacions estacionals del nivell "
        "d'aigua en funcio de les condicions climatiques."
    )

    # === 3.4 AGRESSIVITAT - Templates (EHE-08) ===
    AGRESSIVITAT_INTRO = (
        "S'han realitzat assaigs de laboratori per determinar el contingut "
        "en sulfats solubles del terreny, d'acord amb la norma UNE 83963."
    )

    AGRESSIVITAT_RESULT_TEMPLATE = (
        "El contingut en sulfats del terreny es de {sulfate:.0f} mg/kg, "
        "el que classifica el terreny com a {classification}."
    )

    AGRESSIVITAT_NO_DATA = (
        "[PENDENT: Resultats d'assaig de sulfats]\n\n"
        "No es disposa de dades de contingut en sulfats. "
        "Es recomana realitzar l'assaig corresponent."
    )

    # EHE-08 thresholds for sulfate classification
    SULFATE_THRESHOLDS = {
        'no_aggressive': (0, 2000, '', 'no agressiu al formigo'),
        'weak': (2000, 3000, 'Qa', 'debilment agressiu al formigo (classe Qa)'),
        'medium': (3000, 12000, 'Qb', 'moderadament agressiu al formigo (classe Qb)'),
        'strong': (12000, float('inf'), 'Qc', 'fortament agressiu al formigo (classe Qc)'),
    }

    # === 3.5 EXCAVABILITAT - Templates ===
    # N20-based rippability classification (standard geotechnical practice)
    # Lower N20 = easier excavation, Higher N20 = may need special equipment
    RIPPABILITY_THRESHOLDS = {
        # (min_n20, max_n20): (difficulty, equipment, notes)
        (0, 15): ('fàcil', 'retroexcavadora convencional', 'sense necessitat d\'equips especials'),
        (15, 30): ('mitjana', 'retroexcavadora convencional', 'pot requerir ripper en zones més compactes'),
        (30, 50): ('difícil', 'retroexcavadora amb ripper o martell hidràulic', 'materials compactes'),
        (50, 1000): ('molt difícil', 'martell hidràulic o voladura controlada', 'materials molt densos o cimentats'),
    }

    EXCAVABILITAT_INTRO = (
        "A continuació s'avalua la ripabilitat dels materials del subsòl "
        "en funció de les seves característiques geotècniques i els resultats "
        "dels assaigs de penetració dinàmica realitzats."
    )

    EXCAVABILITAT_LEVEL_TEMPLATE = (
        "Els materials del {level_desc} ({material_type}), amb un N20 mitjà de {n20:.0f} cops, "
        "presentaran una dificultat d'excavació {difficulty}, podent-se realitzar les excavacions "
        "amb {equipment}."
    )

    EXCAVABILITAT_SINGLE_TEMPLATE = (
        "Els materials del subsòl ({material_type}), amb un N20 mitjà de {n20:.0f} cops, "
        "no presentaran problemes des del punt de vista de la seva ripabilitat, "
        "podent-se realitzar les excavacions amb {equipment} {notes}."
    )

    EXCAVABILITAT_MULTI_TEMPLATE = (
        "Els materials del primer nivell en els primers {depth:.1f} metres ({material_type_1}) "
        "no presentaran problemes des del punt de vista de la seva ripabilitat, "
        "podent-se realitzar les excavacions amb maquinària convencional. "
        "{deeper_assessment}"
    )

    EXCAVABILITAT_DEEPER_EASY = (
        "En cas d'arribar a major fondària, els materials subjacents ({material_type}) "
        "també permeten l'excavació amb mitjans convencionals."
    )

    EXCAVABILITAT_DEEPER_HARDER = (
        "En cas d'arribar a major fondària, cal tenir en compte que els materials subjacents "
        "({material_type}, N20 = {n20:.0f} cops) presentaran una dificultat d'excavació {difficulty}, "
        "requerint possiblement {equipment}."
    )

    EXCAVABILITAT_RECOMMENDATION = (
        "\n\nEs recomana adaptar la maquinària d'excavació a les condicions reals del terreny "
        "observades durant l'execució de l'obra."
    )

    EXCAVABILITAT_PLACEHOLDER = (
        "L'excavabilitat del terreny dependrà de les característiques "
        "dels materials presents. Es recomana avaluar la ripabilitat "
        "en funció dels resultats dels assaigs de camp."
    )

    # === 3.6 SISMICA - Templates ===
    SISMICA_INTRO = (
        "D'acord amb la Norma de Construccio Sismorresistent NCSE-02, "
        "s'ha de considerar l'accio sismica en el disseny de l'estructura."
    )

    SISMICA_FORMULAS = (
        "Els parametres sismics de disseny son:\n\n"
        "- Acceleracio sismica basica: ab = {ab} g\n"
        "- Coeficient de contribucio: K = 1.0\n"
        "- Coeficient d'amplificacio del terreny: S = {S}\n"
        "- Acceleracio sismica de calcul: ac = S * rho * ab\n\n"
        "On rho es el coeficient adimensional de risc (1.0 per a "
        "construccions d'importancia normal)."
    )

    SISMICA_AB_PLACEHOLDER = "[PENDENT: Consultar ab per al municipi]"
    SISMICA_S_DEFAULT = "1.0"  # Conservative default for T-1 soils

    # === 3.7 RADO - Templates ===
    RADO_INTRO = (
        "Segons el mapa de potencial de rado d'Espanya elaborat pel "
        "Consell de Seguretat Nuclear (CSN), el municipi es classifica "
        "dins la zona de potencial de rado:"
    )

    RADO_ZONE_PLACEHOLDER = (
        "[PENDENT: Consultar zona de rado per al municipi]\n\n"
        "Les zones es classifiquen en:\n"
        "- ZONA 0: Potencial baix (<300 Bq/m3)\n"
        "- ZONA 1: Potencial mitja (300-600 Bq/m3)\n"
        "- ZONA 2: Potencial alt (>600 Bq/m3)"
    )

    RADO_ZONE_TEMPLATE = (
        "ZONA {zone}: Potencial {level}\n\n"
        "{recommendation}"
    )

    RADO_RECOMMENDATIONS = {
        0: "No es requereixen mesures especifiques de proteccio contra el rado.",
        1: "Es recomana considerar mesures basiques de ventilacio en soterranis.",
        2: "Es requereixen mesures de proteccio contra el rado segons el CTE DB HS6.",
    }

    # Permeability lookup by material type
    PERMEABILITY_TABLE = {
        'graves': ('Alta', '10^-2 a 10^-4'),
        'sorres': ('Mitjana-Alta', '10^-3 a 10^-5'),
        'llims': ('Baixa', '10^-5 a 10^-7'),
        'argiles': ('Molt baixa', '10^-7 a 10^-9'),
        'granular': ('Mitjana-Alta', '10^-3 a 10^-5'),  # Default for granular soils
    }

    FALLBACK_VALUE = "-"

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

    # === 3.1 MARC GEOLOGIC ===

    def generate_marc_geologic(self) -> str:
        """
        Generate regional geology text (3.1).

        Priority:
        1. Eva's municipality-specific template (.docx) — if historia_geologica_template set
        2. ICGC WMS API + hardcoded regional templates (existing flow)

        Returns:
            Complete regional geology text, or placeholder if data unavailable
        """
        # Try Eva's template first (from auto-extractor or wizard)
        historia_path = getattr(self.data, 'historia_geologica_template', '')
        if historia_path:
            try:
                from ..historia_geologica import extract_paragraphs
                eva_paras = extract_paragraphs(historia_path)
                if eva_paras:
                    logger.info(f"Using Eva's historia geologica template: {historia_path}")
                    return self._build_marc_geologic_from_eva(eva_paras)
            except Exception as e:
                logger.warning(f"Historia geologica template failed: {e}")

        # Existing flow: ICGC WMS + hardcoded regional templates
        # Get unit via cached method (checks manual override first)
        unit = self._get_icgc_unit_cached()

        if not unit:
            if not self.data.utm_x or not self.data.utm_y:
                logger.warning("No UTM coordinates and no manual ICGC override")
                return self._generate_marc_geologic_fallback(
                    "No es disposa de coordenades UTM per consultar l'ICGC."
                )
            else:
                return self._generate_marc_geologic_fallback(
                    "No s'ha pogut obtenir informació geològica de l'ICGC."
                )

        logger.info(f"ICGC unit: {unit.code} - {unit.description}")

        # Determine geological region
        region = self._get_region_cached()
        logger.info(f"Determined geological region: {region}")

        # Get regional template paragraphs
        regional_paragraphs = self._load_regional_template(region)
        if not regional_paragraphs:
            logger.warning(f"No template for region '{region}', using generic")
            return self._generate_marc_geologic_with_icgc_only(unit)

        # Build complete text: regional paragraphs + ICGC unit paragraph
        paragraphs = regional_paragraphs.copy()

        # Add paragraph 6: ICGC unit reference
        icgc_paragraph = unit.format_for_report()
        paragraphs.append(icgc_paragraph)

        return "\n\n".join(paragraphs)

    def _build_marc_geologic_from_eva(self, eva_paras: list[str]) -> str:
        """
        Build marc geologic text from Eva's template paragraphs + ICGC unit.

        Fits Eva's paragraphs into slots 1-5 (merging overflow into slot 5),
        then appends ICGC unit reference as the final paragraph.
        """
        MAX_SLOTS = 5
        if len(eva_paras) > MAX_SLOTS:
            # Merge overflow into slot 5
            paras = eva_paras[:MAX_SLOTS - 1]
            paras.append('\n\n'.join(eva_paras[MAX_SLOTS - 1:]))
        else:
            paras = eva_paras.copy()

        # Append ICGC unit reference as final paragraph
        unit = self._get_icgc_unit_cached()
        if unit:
            paras.append(unit.format_for_report())

        return "\n\n".join(paras)

    def _load_regional_template(self, region: str) -> list[str]:
        """
        Load regional template paragraphs.

        Checks hardcoded REGIONAL_TEMPLATES first (primary source),
        falls back to markdown file if not found.

        Args:
            region: Region identifier (e.g., 'depressio_ebre')

        Returns:
            List of paragraph strings, or empty list if not found
        """
        # Primary source: hardcoded templates (tested and verified)
        if region in self.REGIONAL_TEMPLATES:
            return self.REGIONAL_TEMPLATES[region]

        # Fallback: try loading from markdown file
        template_path = self.TEMPLATES_DIR / f"{region}.md"
        if not template_path.exists():
            logger.debug(f"No template file found at {template_path}")
            return []

        try:
            content = template_path.read_text(encoding='utf-8')
            paragraphs = self._parse_markdown_template(content)
            if paragraphs:
                logger.info(f"Loaded {len(paragraphs)} paragraphs from {template_path}")
            return paragraphs
        except Exception as e:
            logger.warning(f"Error loading template from {template_path}: {e}")
            return []

    def _parse_markdown_template(self, content: str) -> list[str]:
        """
        Parse markdown template content into paragraph list.

        Expects format with `## Paràgraf N:` headers separating paragraphs.

        Args:
            content: Raw markdown file content

        Returns:
            List of paragraph text strings
        """
        import re

        paragraphs = []
        # Split on paragraph headers (## Paràgraf N: ...)
        pattern = r'##\s*Paràgraf\s+\d+[^#]*'
        matches = re.findall(pattern, content, re.IGNORECASE)

        for match in matches:
            # Remove the header line and clean up
            lines = match.strip().split('\n')
            # Skip the header line (first line with ## Paràgraf)
            body_lines = [line.strip() for line in lines[1:] if line.strip()]
            if body_lines:
                # Join non-empty lines into a single paragraph
                paragraph = ' '.join(body_lines)
                paragraphs.append(paragraph)

        return paragraphs

    def _generate_marc_geologic_fallback(self, error_msg: str) -> str:
        """
        Generate fallback text when ICGC data unavailable.

        Args:
            error_msg: Specific error message to include

        Returns:
            Placeholder text with error context
        """
        return (
            f"[PENDENT: Text de marc geològic regional]\n\n"
            f"{error_msg}\n\n"
            f"{self._MANUAL_INSTRUCTION_SUFFIX}"
        )

    def _generate_marc_geologic_with_icgc_only(self, unit: GeologicalUnit) -> str:
        """
        Generate text when we have ICGC data but no regional template.

        Args:
            unit: Geological unit from ICGC

        Returns:
            Basic geological context from ICGC data
        """
        return (
            f"[NOTA: Plantilla regional no disponible]\n\n"
            f"{unit.format_for_report()}\n\n"
            f"Per a un text complet de marc geològic, cal afegir la descripció "
            f"del context regional (evolució tectònica, sedimentació, etc.). "
            f"{self._MANUAL_INSTRUCTION_SUFFIX}"
        )

    def generate_figura4_reference(self) -> str:
        """Generate reference to Figure 4 (geological map)."""
        return "[FIGURA 4: Mapa geologic de la zona (ICGC)]"

    # === 3.2 MATERIALS ===

    def generate_materials_intro(self) -> str:
        """
        Generate materials introduction paragraph (3.2).

        Returns:
            Introduction text with level count from DPSH interpretation
        """
        num_levels = len(self.data.soil_levels) if self.data.soil_levels else 1

        return self.MATERIALS_INTRO_TEMPLATE.format(
            num_levels=num_levels,
            nivell_word=self._pluralize(num_levels, "nivell", "nivells"),
            plural="" if num_levels == 1 else "s",
        )

    def _get_n20_classification(self, n20: float) -> tuple[str, str, str]:
        """
        Classify N20 value into consistency and bearing capacity categories.

        Args:
            n20: Average N20 blow count

        Returns:
            Tuple of (consistency, bearing_capacity, granular_description)
        """
        for (min_val, max_val), (consistency, bearing, granular) in self.N20_THRESHOLDS.items():
            if min_val <= n20 < max_val:
                return consistency, bearing, granular
        return 'variable', 'variable', 'de compacitat variable'

    def _get_icgc_unit_cached(self) -> GeologicalUnit | None:
        """Get ICGC unit, caching the result for reuse.

        Priority: manual override (user_data) > WMS 1:50k query.
        """
        if not hasattr(self, '_cached_icgc_unit'):
            self._cached_icgc_unit = None
            # Check for manual override (e.g., from 1:25k map lookup)
            if self.data.icgc_unit_code:
                self._cached_icgc_unit = GeologicalUnit(
                    code=self.data.icgc_unit_code,
                    description=self.data.icgc_unit_description or '',
                    era='',
                    period='',
                    epoch=self.data.icgc_unit_epoch or '',
                    raw_response='manual_override',
                )
                logger.info(
                    f"Using manual ICGC unit override: {self.data.icgc_unit_code}"
                )
            elif self.data.utm_x and self.data.utm_y:
                try:
                    self._cached_icgc_unit = get_geological_unit(
                        utm_x=self.data.utm_x,
                        utm_y=self.data.utm_y,
                        use_cache=True,
                    )
                except ICGCError as e:
                    logger.warning(f"Could not get ICGC unit: {e}")
        return self._cached_icgc_unit

    def _get_region_cached(self) -> str:
        """Get geological region, caching the result for reuse."""
        if not hasattr(self, '_cached_region'):
            unit = self._get_icgc_unit_cached()
            self._cached_region = determine_region(unit, self.data.municipality)
        return self._cached_region

    def generate_materials_levels(self) -> list[str]:
        """
        Generate level descriptions (3.2) using ICGC data and regional templates.

        Returns:
            List of level description strings
        """
        levels = []

        if not self.data.soil_levels:
            levels.append(self.MATERIALS_LEVEL_PLACEHOLDER.format(level_num=1))
            return levels

        # Get ICGC unit and region for template selection
        icgc_unit = self._get_icgc_unit_cached()
        region = self._get_region_cached()

        # Get regional templates (default to depressio_ebre)
        region_templates = self.MATERIALS_TEMPLATES.get(
            region, self.MATERIALS_TEMPLATES['depressio_ebre']
        )

        for i, level in enumerate(self.data.soil_levels):
            # Determine material type from description
            material_type = self._identify_material_type(level.description)
            is_granular = material_type in ('graves', 'sorres', 'granular')

            # Select appropriate template
            template_key = 'granular' if is_granular else 'cohesiu'
            template_data = region_templates.get(template_key, region_templates['granular'])

            # Get N20 classification
            consistency, bearing, _ = self._get_n20_classification(level.n20_average)

            # Format depth range
            if i == 0:
                depth_start = "superficialment"
            else:
                prev_level = self.data.soil_levels[i - 1]
                depth_start = f"a partir de {prev_level.depth_to_m:.2f} m"

            if level.thickness_m:
                depth_range = f"{depth_start} i fins a {level.depth_to_m:.2f} m, amb un gruix de {level.thickness_m:.2f} m"
            else:
                depth_range = f"{depth_start} i fins a la cota de finalització dels assaigs"

            # Surface note for first level
            surface_note = ""
            if i == 0:
                if self.data.is_anthropized:
                    surface_note = (
                        "Superficialment es detecta un tram de sòl vegetal i/o "
                        "materials antropitzats de petit gruix."
                    )
                else:
                    surface_note = (
                        "Superficialment es detecta un tram de sòl vegetal "
                        "de petit gruix."
                    )

            # Get lithology from DPSH description or ICGC
            lithology = level.description.lower()
            if not lithology or lithology == "sense descripció":
                if icgc_unit:
                    # Extract main lithology from ICGC description
                    lithology = icgc_unit.description.split('(')[0].strip().lower()
                else:
                    lithology = "materials granulars" if is_granular else "materials cohesius"

            # Get epoch from ICGC or use generic
            epoch = "quaternaris"
            icgc_code = "Qx"
            if icgc_unit:
                epoch = icgc_unit.epoch.lower() if icgc_unit.epoch else "quaternaris"
                icgc_code = icgc_unit.code

            # Format the level text
            try:
                level_text = template_data['template'].format(
                    level_num=level.level_number,
                    lithology=lithology,
                    colors=template_data['colors'],
                    characteristics=template_data['characteristics'],
                    surface_note=surface_note,
                    epoch=epoch,
                    icgc_code=icgc_code,
                    depth_range=depth_range,
                    n20_avg=level.n20_average,
                    bearing=bearing,
                    consistency=consistency,
                )
            except KeyError as e:
                logger.warning(f"Template formatting error: {e}")
                level_text = self.MATERIALS_LEVEL_PLACEHOLDER.format(level_num=level.level_number)

            levels.append(level_text)

        return levels

    def generate_depth_texts(self) -> list[str]:
        """
        Generate per-level depth/location paragraphs ("Localitzacio").

        For each soil level, describes where the level is found in terms
        of depth range and thickness based on DPSH test results.

        Returns:
            List of depth description strings, one per soil level
        """
        texts = []
        if not self.data.soil_levels:
            return texts

        # Check if any test reached refusal
        any_refusal = False
        if self.data.dpsh and self.data.dpsh.tests:
            any_refusal = any(t.refusal_reached for t in self.data.dpsh.tests)

        num_levels = len(self.data.soil_levels)

        for i, level in enumerate(self.data.soil_levels):
            is_last = (i == num_levels - 1)

            # Depth end description
            if is_last and any_refusal and level.depth_to_m is None:
                depth_end = (
                    "fins a la cota de finalització dels assaigs "
                    "(rebuig a la penetració)"
                )
            elif level.depth_to_m is not None:
                depth_end = f"fins a {level.depth_to_m:.2f} m de profunditat"
            else:
                depth_end = (
                    "fins a la cota de finalització de tots els assaigs"
                )

            # Thickness note
            if level.thickness_m is not None:
                thickness_note = (
                    f", amb potències estudiades de {level.thickness_m:.2f} metres"
                )
            else:
                thickness_note = (
                    ", amb potències estudiades de com a mínim "
                    f"{abs(level.depth_from_m - (level.depth_to_m if level.depth_to_m is not None else level.depth_from_m)):.2f} metres"
                    if level.depth_to_m is not None
                    else ""
                )

            # Build sentence based on position
            if level.level_number == 1:
                text = (
                    "A partir dels assaigs realitzats, aquest nivell es detecta "
                    f"superficialment i {depth_end}{thickness_note}."
                )
            else:
                text = (
                    "A partir dels assaigs realitzats, aquest nivell es detecta "
                    f"a partir de {level.depth_from_m:.2f} m i {depth_end}"
                    f"{thickness_note}."
                )

            texts.append(text)

        return texts

    def generate_geomech_texts(self) -> list[str]:
        """
        Generate per-level geomechanical paragraphs ("Resistencia").

        For each soil level, describes geomechanical properties including
        material character, bearing capacity, and N20 averages.

        Returns:
            List of geomechanical description strings, one per soil level
        """
        texts = []
        if not self.data.soil_levels:
            return texts

        # Check per-level refusal from DPSH readings
        any_refusal = False
        if self.data.dpsh and self.data.dpsh.tests:
            any_refusal = any(t.refusal_reached for t in self.data.dpsh.tests)

        num_levels = len(self.data.soil_levels)

        for i, level in enumerate(self.data.soil_levels):
            material_type = self._identify_material_type(level.description)
            is_granular = material_type in ('graves', 'sorres', 'granular')
            character = "granular" if is_granular else "cohesiu"

            _, bearing, _ = self._get_n20_classification(level.n20_average)

            # Refusal note for last level with high N20
            is_last = (i == num_levels - 1)
            if is_last and any_refusal:
                refusal_note = (
                    ", assolint rebuig a la penetració pels trams més profunds"
                )
            else:
                refusal_note = ""

            if is_granular:
                property_phrase = "densitat i una capacitat"
            else:
                property_phrase = "consistència i una capacitat"

            text = (
                "Des del punt de vista geomecànic es tracta d'uns materials "
                f"de caràcter {character}, amb una {property_phrase} "
                f"portant {bearing}. Dels assaigs de penetració dinàmica DPSH "
                f"s'obté un valor de Nb mig de {level.n20_average:.0f} cops"
                f"{refusal_note}."
            )

            texts.append(text)

        return texts

    def generate_sample_photos(self) -> list[str]:
        """
        Get list of sample photo references for Section 3.

        Returns:
            List of photo reference placeholders
        """
        photos = []

        if self.data.soil_levels:
            for i, level in enumerate(self.data.soil_levels, 1):
                photos.append(f"[FOTO {i}: Mostra del nivell {level.level_number}]")
        else:
            photos.append("[FOTO: Mostra del terreny]")

        return photos

    # === 3.3 HIDROGEOLOGIA ===

    def generate_hidrogeologia_surface(self) -> str:
        """
        Generate surface hydrology text (3.3).

        Returns:
            Urban or rural surface hydrology template
        """
        if self.data.is_urban:
            return self.HIDROGEOLOGIA_SURFACE_URBAN
        return self.HIDROGEOLOGIA_SURFACE_RURAL

    def generate_hidrogeologia_groundwater(self) -> str:
        """
        Generate groundwater statement (3.3).

        Uses DPSH water detection data when available.

        Returns:
            Groundwater presence/absence statement
        """
        if self.data.water_detected:
            depth = self._get_water_depth()
            if depth is not None:
                return self.HIDROGEOLOGIA_WATER_DETECTED.format(depth=depth)
            return (
                "Durant l'execucio dels treballs de camp s'ha detectat presencia "
                "de nivell freatic (fondaria no determinada amb precisio)."
            )
        return self.HIDROGEOLOGIA_WATER_NOT_DETECTED

    def _get_water_depth(self) -> float | None:
        """Get water depth from DPSH data if available."""
        if not self.data.dpsh or not self.data.dpsh.tests:
            return None

        for test in self.data.dpsh.tests:
            for reading in test.readings:
                if reading.water_level:
                    return abs(reading.depth_m)
        return None

    def generate_taula7_permeability(self) -> list[PermeabilityRow]:
        """
        Generate permeability table (Taula 7).

        Returns:
            List of PermeabilityRow for each identified material
        """
        rows = []

        if self.data.soil_levels:
            for level in self.data.soil_levels:
                # Try to match material type from description
                material_type = self._identify_material_type(level.description)
                perm_data = self.PERMEABILITY_TABLE.get(
                    material_type,
                    self.PERMEABILITY_TABLE['granular']
                )

                rows.append(PermeabilityRow(
                    material=level.description,
                    permeabilitat=perm_data[0],
                    k_m_s=perm_data[1],
                ))
        else:
            # Default row with placeholder
            rows.append(PermeabilityRow(
                material="[Material no determinat]",
                permeabilitat=self.FALLBACK_VALUE,
                k_m_s=self.FALLBACK_VALUE,
            ))

        return rows

    def _identify_material_type(self, description: str) -> str:
        """
        Identify material type from description for permeability lookup.

        Args:
            description: Soil level description

        Returns:
            Material type key for permeability lookup
        """
        desc_lower = description.lower()

        if 'grava' in desc_lower or 'graves' in desc_lower:
            return 'graves'
        if 'sorra' in desc_lower or 'sorres' in desc_lower:
            return 'sorres'
        if 'llim' in desc_lower:
            return 'llims'
        if 'argila' in desc_lower or 'argiles' in desc_lower:
            return 'argiles'

        # Default to granular for most construction soils
        return 'granular'

    # === 3.4 AGRESSIVITAT ===

    def generate_agressivitat(self) -> str:
        """
        Generate aggressivity section text (3.4).

        Classifies soil aggressivity based on sulfate content per EHE-08.

        Returns:
            Complete aggressivity section text with classification
        """
        if self.data.sulfate_mg_kg is None:
            return self.AGRESSIVITAT_NO_DATA

        sulfate = self.data.sulfate_mg_kg
        agg_class, classification = self.classify_aggressivity(sulfate)

        result = self.AGRESSIVITAT_INTRO + "\n\n"
        result += self.AGRESSIVITAT_RESULT_TEMPLATE.format(
            sulfate=sulfate,
            classification=classification,
        )

        # Add recommendations based on class
        if agg_class == 'Qa':
            result += (
                "\n\nNo es requereix l'us de ciment especial segons EHE-08."
            )
        elif agg_class == 'Qb':
            result += (
                "\n\nEs recomana l'us de ciment tipus SR (sulforesistent) "
                "per als elements de formigo en contacte amb el terreny."
            )
        elif agg_class == 'Qc':
            result += (
                "\n\nEs obligatori l'us de ciment tipus SR (sulforesistent) "
                "i es recomana considerar mesures addicionals de proteccio "
                "per als elements de formigo en contacte amb el terreny."
            )

        return result

    @staticmethod
    def classify_aggressivity(sulfate_mg_kg: float) -> tuple[str, str]:
        """
        Classify soil aggressivity based on sulfate content (EHE-08).

        Args:
            sulfate_mg_kg: Sulfate content in mg/kg

        Returns:
            Tuple of (class_code, class_text)
            - class_code: '', 'Qa', 'Qb', or 'Qc'
            - class_text: Human-readable classification
        """
        if sulfate_mg_kg < 2000:
            return ('', 'no agressiu al formigo')
        elif sulfate_mg_kg < 3000:
            return ('Qa', 'debilment agressiu al formigo (classe Qa)')
        elif sulfate_mg_kg < 12000:
            return ('Qb', 'moderadament agressiu al formigo (classe Qb)')
        else:
            return ('Qc', 'fortament agressiu al formigo (classe Qc)')

    # === 3.5 EXCAVABILITAT ===

    def _get_rippability(self, n20: float) -> tuple[str, str, str]:
        """
        Get rippability classification based on N20 value.

        Args:
            n20: Average N20 blow count

        Returns:
            Tuple of (difficulty, equipment, notes)
        """
        for (min_val, max_val), (difficulty, equipment, notes) in self.RIPPABILITY_THRESHOLDS.items():
            if min_val <= n20 < max_val:
                return difficulty, equipment, notes
        return 'variable', 'maquinària adaptada', 'segons condicions reals'

    def _format_material_type_catalan(self, material_type: str, description: str) -> str:
        """Format material type for Catalan text."""
        type_map = {
            'graves': 'graves',
            'sorres': 'sorres',
            'granular': 'materials granulars',
            'argiles': 'argiles',
            'llims': 'llims',
        }
        # Use description if available, otherwise use mapped type
        if description and description.lower() not in ('sense descripció', ''):
            return description.lower()
        return type_map.get(material_type, 'materials del subsòl')

    def generate_excavabilitat(self) -> str:
        """
        Generate excavability section text (3.5).

        Provides N20-based rippability assessment for each soil level,
        with specific equipment recommendations.

        Returns:
            Excavability assessment based on material type and N20 values
        """
        if not self.data.soil_levels:
            return self.EXCAVABILITAT_PLACEHOLDER

        result = self.EXCAVABILITAT_INTRO + "\n\n"

        # Single level case
        if len(self.data.soil_levels) == 1:
            level = self.data.soil_levels[0]
            material_type = self._identify_material_type(level.description)
            material_desc = self._format_material_type_catalan(material_type, level.description)
            difficulty, equipment, notes = self._get_rippability(level.n20_average)

            result += self.EXCAVABILITAT_SINGLE_TEMPLATE.format(
                material_type=material_desc,
                n20=level.n20_average,
                difficulty=difficulty,
                equipment=equipment,
                notes=notes,
            )
            result += self.EXCAVABILITAT_RECOMMENDATION
            return result

        # Multiple levels case
        first_level = self.data.soil_levels[0]
        material_type_1 = self._identify_material_type(first_level.description)
        material_desc_1 = self._format_material_type_catalan(material_type_1, first_level.description)
        difficulty_1, equipment_1, _ = self._get_rippability(first_level.n20_average)

        # Check deeper levels
        deeper_assessments = []
        for level in self.data.soil_levels[1:]:
            material_type = self._identify_material_type(level.description)
            material_desc = self._format_material_type_catalan(material_type, level.description)
            difficulty, equipment, _ = self._get_rippability(level.n20_average)

            if difficulty in ('fàcil', 'mitjana'):
                deeper_assessments.append(
                    self.EXCAVABILITAT_DEEPER_EASY.format(material_type=material_desc)
                )
            else:
                deeper_assessments.append(
                    self.EXCAVABILITAT_DEEPER_HARDER.format(
                        material_type=material_desc,
                        n20=level.n20_average,
                        difficulty=difficulty,
                        equipment=equipment,
                    )
                )

        # Build the multi-level text
        deeper_text = " ".join(deeper_assessments) if deeper_assessments else ""

        result += self.EXCAVABILITAT_MULTI_TEMPLATE.format(
            depth=first_level.depth_to_m if first_level.thickness_m else 1.5,
            material_type_1=material_desc_1,
            deeper_assessment=deeper_text,
        )
        result += self.EXCAVABILITAT_RECOMMENDATION

        return result

    # === 3.6 SISMICA ===

    # Verification warning for unknown municipalities
    SISMICA_VERIFICATION_WARNING = (
        "\n\n⚠️ VERIFICACIÓ REQUERIDA: El municipi '{municipality}' no es troba "
        "a la taula de consulta. El valor ab = {ab} g és un valor per defecte. "
        "Si us plau, verifiqueu l'acceleració sísmica bàsica a l'Annex 1 de la NCSE-02."
    )

    def generate_sismica(self) -> str:
        """
        Generate seismic parameters section text (3.6).

        Uses municipality lookup table for ab (basic seismic acceleration)
        from NCSE-02 Annex 1.

        Returns:
            Complete seismic section text with ab value
        """
        result = self.SISMICA_INTRO + "\n\n"

        # Get ab value from municipality lookup (with status)
        seismic_result = get_seismic_ab_with_status(self.data.municipality or "")
        ab = seismic_result.ab
        ab_str = f"{ab:.2f}"

        # Determine S coefficient based on soil class
        if self.data.cte_soil_class == "T-1":
            S = "1.0"
            S_val = 1.0
        elif self.data.cte_soil_class == "T-2":
            S = "1.2"
            S_val = 1.2
        else:
            S = "1.4"
            S_val = 1.4

        result += self.SISMICA_FORMULAS.format(
            ab=ab_str,
            S=S,
        )

        # Calculate ac (seismic calculation acceleration)
        # ac = S * rho * ab, where rho = 1.0 for normal importance
        rho = 1.0
        ac = S_val * rho * ab

        # Add clarification about norm applicability
        if not is_seismic_norm_required(ab):
            result += (
                f"\n\nCal indicar que l'aplicació de la norma sismorresistent "
                f"no és obligatòria en el cas d'edificis d'importància normal "
                f"quan l'acceleració sísmica de càlcul sigui inferior a 0,08 g. "
                f"En aquest cas, ac = {S} × 1,0 × {ab_str} = {ac:.2f} g < 0,08 g, "
                f"per tant no és obligatòria l'aplicació de la NCSE-02."
            )
        else:
            result += (
                f"\n\nEn aquest cas, l'acceleració sísmica de càlcul és "
                f"ac = {S} × 1,0 × {ab_str} = {ac:.2f} g ≥ 0,08 g, "
                f"per tant és obligatòria l'aplicació de la NCSE-02."
            )

        # Add verification warning if municipality not found in lookup table
        if not seismic_result.found and self.data.municipality:
            result += self.SISMICA_VERIFICATION_WARNING.format(
                municipality=self.data.municipality,
                ab=ab_str,
            )

        return result

    # === 3.7 RADO ===

    # Verification warning for unknown municipalities
    RADO_VERIFICATION_WARNING = (
        "\n\n⚠️ VERIFICACIÓ REQUERIDA: El municipi '{municipality}' no es troba "
        "a la taula de consulta. La zona {zone} (potencial {level}) és un valor per defecte. "
        "Si us plau, verifiqueu la classificació de radó a l'Apèndix B del RD 732/2019."
    )

    def generate_rado(self) -> str:
        """
        Generate radon zone section text (3.7).

        Uses municipality lookup table for radon zone classification
        from RD 732/2019 (CTE DB HS6).

        Returns:
            Complete radon section text with zone and recommendations
        """
        result = self.RADO_INTRO + "\n\n"

        # Get radon info from municipality lookup (with status)
        radon_result = get_radon_info_with_status(self.data.municipality or "")
        radon_info = radon_result.info

        # Format zone information
        result += self.RADO_ZONE_TEMPLATE.format(
            zone=radon_info.zone,
            level=radon_info.level,
            recommendation=radon_info.recommendation,
        )

        # Add municipality reference
        if self.data.municipality:
            result += (
                f"\n\nLa parcel·la concreta d'estudi es localitza al terme municipal de "
                f"{self.data.municipality.upper()} i, segons la taula existent a l'apèndix B "
                f"del RD 732/2019, pertany a la ZONA {radon_info.zone}, "
            )
            if radon_info.zone == 0:
                result += "municipi amb baixes concentracions de gas radó."
            elif radon_info.zone == 1:
                result += (
                    "municipi amb concentracions mitjanes de gas radó en edificis tancats. "
                    "Es recomana la implementació de mesures bàsiques de protecció."
                )
            else:  # zone == 2
                result += (
                    "municipi amb concentracions potencialment elevades de gas radó en edificis tancats. "
                    "És obligatòria la implementació de mesures de protecció segons CTE DB HS6."
                )

        # Add verification warning if municipality not found in lookup table
        if not radon_result.found and self.data.municipality:
            result += self.RADO_VERIFICATION_WARNING.format(
                municipality=self.data.municipality,
                zone=radon_info.zone,
                level=radon_info.level,
            )

        # Add CSN coordinate-based potential if coordinates available
        if self.data.utm_x and self.data.utm_y:
            try:
                csn_text = get_radon_potential_text(self.data.utm_x, self.data.utm_y)
                if csn_text:
                    result += "\n\n" + csn_text
            except Exception as e:
                logger.warning(f"Could not get CSN radon potential: {e}")

        return result

    # === Generate All ===

    def generate_all(self) -> Section3Content:
        """
        Generate all Section 3 content.

        Returns:
            Section3Content dataclass with all generated content
        """
        return Section3Content(
            # 3.1 MARC GEOLOGIC
            marc_geologic=self.generate_marc_geologic(),
            figura4_reference=self.generate_figura4_reference(),
            # 3.2 MATERIALS
            materials_intro=self.generate_materials_intro(),
            materials_levels=self.generate_materials_levels(),
            sample_photos=self.generate_sample_photos(),
            # 3.3 HIDROGEOLOGIA
            hidrogeologia_surface=self.generate_hidrogeologia_surface(),
            hidrogeologia_groundwater=self.generate_hidrogeologia_groundwater(),
            taula7_permeability=self.generate_taula7_permeability(),
            # 3.4 AGRESSIVITAT
            agressivitat=self.generate_agressivitat(),
            # 3.5 EXCAVABILITAT
            excavabilitat=self.generate_excavabilitat(),
            # 3.6 SISMICA
            sismica=self.generate_sismica(),
            # 3.7 RADO
            rado=self.generate_rado(),
            # Per-level texts
            depth_texts=self.generate_depth_texts(),
            geomech_texts=self.generate_geomech_texts(),
        )


# CLI for testing
if __name__ == '__main__':
    from dataclasses import dataclass as dc
    from dataclasses import field as dc_field
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

    @dc
    class DPSHReading:
        depth_m: float
        n20: int
        nb: float
        water_level: bool = False

    @dc
    class DPSHTest:
        test_id: str
        readings: list = dc_field(default_factory=list)
        refusal_reached: bool = False

    @dc
    class DPSHData:
        expedient: str
        tests: list = dc_field(default_factory=list)
        source_file: str = ""

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
        is_urban: bool = True
        is_sloped: bool = False
        is_anthropized: bool = False
        dpsh: DPSHData | None = None
        soil_levels: list = dc_field(default_factory=list)
        sulfate_mg_kg: float | None = None
        cte_soil_class: str = "T-1"
        utm_x: float | None = None
        utm_y: float | None = None

        @property
        def water_detected(self) -> bool:
            return self.dpsh.any_water_detected if self.dpsh else False

    print("=" * 60)
    print("G3DT Section 3 Generator - Test")
    print("=" * 60)

    # Create test data
    client = ClientData(company_name="Construccions Test SL")

    soil_levels = [
        SoilLevel(
            level_number=1,
            description="Graves i sorres amb matriu llimosa",
            thickness_m=None,
            n20_average=36.0,
        )
    ]

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
        is_urban=True,
        is_sloped=False,
        dpsh=dpsh_data,
        soil_levels=soil_levels,
        sulfate_mg_kg=850.0,
        cte_soil_class="T-1",
    )

    # Generate content
    generator = Section3Generator(test_data)
    content = generator.generate_all()

    # Display results
    print("\n" + "-" * 60)
    print("3.1 MARC GEOLOGIC")
    print("-" * 60)
    print(content.marc_geologic)
    print(f"\n{content.figura4_reference}")

    print("\n" + "-" * 60)
    print("3.2 MATERIALS")
    print("-" * 60)
    print("\n[Intro]")
    print(content.materials_intro)
    print("\n[Level Descriptions]")
    for level in content.materials_levels:
        print(level)
        print()
    print("[Sample Photos]")
    for photo in content.sample_photos:
        print(f"  - {photo}")

    print("\n" + "-" * 60)
    print("3.3 HIDROGEOLOGIA")
    print("-" * 60)
    print("\n[Surface Hydrology]")
    print(content.hidrogeologia_surface)
    print("\n[Groundwater]")
    print(content.hidrogeologia_groundwater)
    print("\n[Taula 7: Permeabilitat]")
    print("  Material | Permeabilitat | k (m/s)")
    print("  " + "-" * 45)
    for row in content.taula7_permeability:
        print(f"  {row.material[:20]} | {row.permeabilitat} | {row.k_m_s}")

    print("\n" + "-" * 60)
    print("3.4 AGRESSIVITAT")
    print("-" * 60)
    print(content.agressivitat)

    print("\n" + "-" * 60)
    print("3.5 EXCAVABILITAT")
    print("-" * 60)
    print(content.excavabilitat)

    print("\n" + "-" * 60)
    print("3.6 SISMICA")
    print("-" * 60)
    print(content.sismica)

    print("\n" + "-" * 60)
    print("3.7 RADO")
    print("-" * 60)
    print(content.rado)

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)

    # Test aggressivity classification
    print("\n--- Aggressivity Classification Test ---")
    test_values = [500, 1500, 2500, 5000, 15000]
    for val in test_values:
        code, text = Section3Generator.classify_aggressivity(val)
        print(f"  {val} mg/kg -> {code or 'N/A'}: {text}")
