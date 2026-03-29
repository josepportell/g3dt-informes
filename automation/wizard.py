#!/usr/bin/env python3
"""
G3DT User Data Wizard

Interactive CLI wizard for generating user_data.json files for geotechnical
reports. Pre-fills values from auto-extraction sources and lets the user
confirm or correct each one.

Usage:
    python3 -m automation.wizard reference-material/4001612-bell-lloc

Author: Eficients.cat
Date: 2026-02-06
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from .cte_geomech import detect_soil_type
from .data_schema import BUILDING_TYPES
from .vision_normalizer import load_dpsh_json, load_sondeig_json

# Maps fuzzy keywords from planol extraction to canonical building types
_BUILDING_TYPE_KEYWORDS = {
    'unifamiliar': BUILDING_TYPES[0],   # Habitatge aïllat
    'aillat': BUILDING_TYPES[0],
    'aïllat': BUILDING_TYPES[0],
    'plurifamiliar': BUILDING_TYPES[1],  # Habitatge plurifamiliar
    'nau': BUILDING_TYPES[2],            # Nau industrial
    'industrial': BUILDING_TYPES[2],
    'comercial': BUILDING_TYPES[3],      # Edifici comercial
    'public': BUILDING_TYPES[4],         # Edifici públic
    'públic': BUILDING_TYPES[4],
}

# The 13 wizard fields grouped for display
WIZARD_FIELDS = [
    'architect_name', 'architect_company', 'client_name',
    'street_address', 'site_municipality',
    'building_type',
    'num_floors', 'superficie_construida_m2',
    'superficie_parcela_m2', 'superficie_cadastral_m2', 'building_height_m',
    'site_description', 'access_description',
    'adjacent_north', 'adjacent_south', 'adjacent_east', 'adjacent_west',
    'is_anthropized', 'num_soil_levels', 'soil_types', 'foundation_depth_m',
    'cota_referencia', 'has_basement', 'has_retaining_walls',
    'utm_x', 'utm_y',
]

# Expert override fields (optional, for when auto-detection gives wrong results)
EXPERT_ICGC_FIELDS = ['icgc_unit_code', 'icgc_unit_description', 'icgc_unit_epoch']
EXPERT_GEOMECH_FIELDS = ['gamma', 'cohesion', 'phi', 'E']
EXPERT_SETTLEMENT_FIELDS = ['Es_settlement']
EXPERT_HISTORIA_FIELDS = ['historia_geologica_template']


def _split_address(location: str) -> tuple[str, str]:
    """Split a full location into (street, municipality).

    Handles Catalan address formats:
      "Carrer Mestre Ramon Ortiz, 25220 Bell-lloc d'Urgell (Lleida)"
      "C/ Major 5, 25250 Bellpuig"
      "Carrer Nou, 14, 08290 Cerdanyola del Vallès"
      "Passeig de Gràcia, 92, Barcelona"

    Returns (street_only, municipality) where municipality has no postal
    code or province. Used as fallback for old planol_extracted.json files
    that have a single 'location' field instead of split fields.
    """
    import re
    # Strip trailing province in parentheses: "(Lleida)", "(Barcelona)"
    loc = re.sub(r'\s*\([^)]*\)\s*$', '', location.strip())

    # Strategy: find the postal code (5 digits) — everything before it
    # (minus trailing comma/space) is street, everything after is municipality.
    m = re.search(r',?\s*\b(\d{5})\s+(.+)', loc)
    if m:
        street = loc[:m.start()].rstrip(' ,')
        municipality = m.group(2).strip()
        return street, municipality

    # No postal code — split on last comma (city is typically the last part)
    parts = [p.strip() for p in loc.split(',')]
    if len(parts) >= 2:
        last = parts[-1]
        # If last part is just a number, it's the street number, not a city
        if re.match(r'^\d+\s*$', last):
            return loc, ''
        street = ', '.join(parts[:-1])
        return street, last

    return location.strip(), ''


class UserDataWizard:
    """Interactive wizard that walks through 12 user_data fields."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.prefills: dict[str, dict] = {}
        self.user_data: dict = {}
        self._user_data_full: dict = {}

    # === Project info parsing ===

    def _parse_folder_name(self) -> tuple[str, str]:
        """Extract expedient and municipality from the project folder name.

        E.g. '4001612-bell-lloc' -> ('4001612', "Bell-Lloc")
        E.g. '4001612 BELL-LLOC' -> ('4001612', "Bell-Lloc")
        """
        from .folder_utils import parse_folder_name
        return parse_folder_name(self.project_path.name)

    # === Prefill loading ===

    def _set_prefill(
        self, field: str, value: object, source: str, confidence: float | None = None
    ) -> None:
        """Set a prefill only if value is truthy and field not already set."""
        if value is None:
            return
        # For strings, skip empty
        if isinstance(value, str) and not value.strip():
            return
        if field not in self.prefills:
            entry: dict = {'value': value, 'source': source}
            if confidence is not None:
                entry['confidence'] = confidence
            self.prefills[field] = entry

    def load_prefills(self) -> None:
        """Load pre-fill values from all available sources (lowest priority first)."""
        self._load_defaults()
        self._load_dpsh()
        self._load_sondeig()
        self._load_adjacents_visor()
        self._load_planol()
        self._load_docs_intel()
        self._load_existing_user_data()
        # Folder-name municipality as last-resort fallback (lowest priority)
        _, municipality = self._parse_folder_name()
        if municipality:
            self._set_prefill('site_municipality', municipality, 'nom carpeta')
        self._generate_template_prefills()

    def _load_defaults(self) -> None:
        self._set_prefill('is_anthropized', True, 'default estandard')
        self._set_prefill('foundation_depth_m', 0.3, 'default estandard')
        self._set_prefill('num_soil_levels', 1, 'default estandard')
        self._set_prefill('has_basement', False, 'default estandard')
        self._set_prefill('has_retaining_walls', False, 'default estandard')
        # Municipality from folder name is set AFTER all other sources
        # (see load_prefills) because _set_prefill is first-writer-wins.

    def _load_dpsh(self) -> None:
        """Load DPSH-derived prefills from dpsh_extracted.json."""
        path = self.project_path / 'validation' / 'dpsh_extracted.json'
        if not path.exists():
            return
        try:
            data = load_dpsh_json(path)
            overall_conf = data.get('overall_confidence')
            tests = data.get('dpsh_tests', [])
            if not tests:
                return

            source = f"DPSH ({len(tests)} assaigs)"

            # Suggest foundation_depth_m based on shallowest refusal depth.
            # If all tests hit refusal, substrate is consistently present:
            #   shallow refusal (<1.5m) -> 0.3m, mid (<3.0m) -> 0.5m, deep -> 1.0m
            refusal_depths = [
                t.get('refusal_depth_m')
                for t in tests
                if t.get('refusal_detected') and t.get('refusal_depth_m') is not None
            ]
            if refusal_depths and len(refusal_depths) == len(tests):
                min_refusal = min(refusal_depths)
                if min_refusal < 1.5:
                    suggested_depth = 0.3
                elif min_refusal < 3.0:
                    suggested_depth = 0.5
                else:
                    suggested_depth = 1.0
                # Override the default
                self.prefills.pop('foundation_depth_m', None)
                self._set_prefill(
                    'foundation_depth_m', suggested_depth, source, overall_conf
                )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'  [AVIS: error carregant {path.name}: {e}]')

    def _load_sondeig(self) -> None:
        path = self.project_path / 'validation' / 'sondeig_extracted.json'
        if not path.exists():
            return
        try:
            data = load_sondeig_json(path)
            overall_conf = data.get('overall_confidence')
            tests = data.get('sondeig_tests', [])
            if tests:
                best_levels = 0
                best_layers = []
                source_test_id = 'S-1'
                for test in tests:
                    # Prefer num_geological_levels (from "Unitat litològica" column)
                    # over len(layers) which counts individual soil strata
                    geo_levels = test.get('num_geological_levels')
                    layers = test.get('layers', [])
                    n = geo_levels if geo_levels is not None else len(layers)
                    if n > best_levels:
                        best_levels = n
                        best_layers = layers
                        source_test_id = test.get('test_id', 'S-1')
                if best_levels > 0:
                    source = f"sondeig {source_test_id}"
                    # Override the default
                    self.prefills.pop('num_soil_levels', None)
                    self._set_prefill('num_soil_levels', best_levels, source, overall_conf)

                    # Infer soil_type per level from layer descriptions
                    from .cte_geomech import detect_soil_type
                    for i, layer in enumerate(best_layers[:best_levels]):
                        desc = layer.get('description') or layer.get('material') or ''
                        soil_type = detect_soil_type(desc)
                        field = f'soil_type_level_{i + 1}'
                        self._set_prefill(field, soil_type, f'sondeig descripció', overall_conf)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'  [AVÍS: error carregant {path.name}: {e}]')

    def _load_adjacents_visor(self) -> None:
        path = self.project_path / 'validation' / 'adjacents_visor.json'
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            adjacents = data.get('adjacents', {})
            confidence = data.get('confidence', {})
            source = 'visor Cadastre'
            for direction in ('north', 'south', 'east', 'west'):
                field = f'adjacent_{direction}'
                val = adjacents.get(direction)
                conf = confidence.get(direction)
                self._set_prefill(field, val, source, conf)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'  [AVÍS: error carregant {path.name}: {e}]')

    def _load_planol(self) -> None:
        path = self.project_path / 'validation' / 'planol_extracted.json'
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            overall_conf = data.get('overall_confidence')
            arch = data.get('architect_data', {})
            source_file = arch.get('source_file', 'A.01.pdf')
            source = f"planol {source_file}"

            # Core wizard fields
            self._set_prefill('architect_name', arch.get('architect'), source, overall_conf)
            self._set_prefill('architect_company', arch.get('architect_company'), source, overall_conf)
            bt = arch.get('building_type')
            if bt:
                self._set_prefill('building_type', bt, source, overall_conf)

            # Dimensions → wizard fields
            dims = arch.get('dimensions', {})

            # Per-floor surfaces → "280+86" format (grouped by actual floor level)
            # Vision may return sub-zones (PB Habitatge, PB Garatge, PB Porxo) —
            # group by floor prefix and sum within each floor.
            floor_surfaces = dims.get('floor_surfaces', [])
            if floor_surfaces and isinstance(floor_surfaces, list) and len(floor_surfaces) > 0:
                import re as _re
                floor_totals = {}  # ordered dict (Python 3.7+)
                floors_with_null = []  # floors with null area_m2

                footprint = dims.get('building_footprint_m2', {})
                fp_val = footprint.get('pdf_value') if isinstance(footprint, dict) else footprint

                for fs in floor_surfaces:
                    area = fs.get('area_m2')
                    label = (fs.get('floor') or '').upper()

                    # Detect combined floor labels like "PB+PP" BEFORE regex
                    if _re.search(r'[+/]', label) and area is not None:
                        parts = _re.split(r'[+/]', label)
                        parts = [p.strip() for p in parts if p.strip()]
                        if len(parts) >= 2 and fp_val is not None:
                            try:
                                fp = float(fp_val)
                                floor_totals[parts[0]] = floor_totals.get(parts[0], 0) + fp
                                remaining = area - fp
                                if remaining > 0:
                                    per_upper = remaining / (len(parts) - 1)
                                    for p in parts[1:]:
                                        floor_totals[p] = floor_totals.get(p, 0) + per_upper
                                # else: footprint >= total, only ground floor
                            except (ValueError, TypeError):
                                floor_totals[parts[0]] = floor_totals.get(parts[0], 0) + area
                        elif len(parts) >= 2:
                            per_floor = area / len(parts)
                            for p in parts:
                                floor_totals[p] = floor_totals.get(p, 0) + per_floor
                        else:
                            floor_totals[label] = floor_totals.get(label, 0) + area
                        continue

                    m = _re.match(r'(P[BSb0-9]+)', label)
                    floor_key = m.group(1) if m else label or 'PB'
                    if area is None:
                        floors_with_null.append(floor_key)
                        continue
                    floor_totals[floor_key] = floor_totals.get(floor_key, 0) + area

                # If a floor has null area, try to derive it from total edificabilitat
                if floors_with_null and floor_totals:
                    planning = arch.get('planning_data', {})
                    total_edif = planning.get('edificabilitat_project_m2')
                    if total_edif is not None:
                        known_sum = sum(floor_totals.values())
                        remaining = total_edif - known_sum
                        if remaining > 0 and len(floors_with_null) == 1:
                            floor_totals[floors_with_null[0]] = remaining

                if floor_totals:
                    sup_expr = '+'.join(str(round(v)) for v in floor_totals.values())
                    self._set_prefill('superficie_construida_m2', sup_expr, source, overall_conf)

            # Fallback: single footprint value (rounded to int)
            if 'superficie_construida_m2' not in self.prefills:
                footprint = dims.get('building_footprint_m2', {})
                footprint_val = footprint.get('pdf_value') if isinstance(footprint, dict) else footprint
                if footprint_val is not None:
                    try:
                        footprint_val = str(round(float(footprint_val)))
                    except (ValueError, TypeError):
                        pass
                    self._set_prefill('superficie_construida_m2', footprint_val, source, overall_conf)

            floors = dims.get('num_floors', {})
            floors_val = floors.get('pdf_value') if isinstance(floors, dict) else floors
            if floors_val is not None:
                from .formatting import format_floor_notation
                self._set_prefill('num_floors', format_floor_notation(str(floors_val)), source, overall_conf)

            # Street address and municipality — prefer new split fields,
            # fall back to old 'location' field with regex splitting
            street = arch.get('street_address')
            municipality = arch.get('municipality')
            if street:
                self._set_prefill('street_address', street, source, overall_conf)
            if municipality:
                self._set_prefill('site_municipality', municipality, source, overall_conf)
            # Backward compat: old planol_extracted.json with single 'location'
            if not street and not municipality:
                location = arch.get('location')
                if location:
                    street, municipality = _split_address(location)
                    self._set_prefill('street_address', street, source, overall_conf)
                    if municipality:
                        self._set_prefill('site_municipality', municipality, source, overall_conf)

            client_from_planol = arch.get('client_name') or arch.get('promotor')
            if client_from_planol:
                self._set_prefill('client_name', client_from_planol, source, overall_conf)

            height = dims.get('max_height_m', {})
            height_val = height.get('pdf_value') if isinstance(height, dict) else height
            if height_val is not None:
                self._set_prefill('building_height_m', height_val, source, overall_conf)

            parcel_area = dims.get('parcel_area_m2', {})
            area_val = parcel_area.get('pdf_value') if isinstance(parcel_area, dict) else parcel_area
            if area_val is not None:
                self._set_prefill('superficie_parcela_m2', area_val, source, overall_conf)

            # Cadastral surface: prefer parcela_projecte_m2 (from JUSTIFICACIO PLANEJAMENT
            # table "Projecte" column) over parcel_area_m2 (from site plan dimensions)
            if 'superficie_cadastral_m2' not in self.prefills:
                projecte_parcel = dims.get('parcela_projecte_m2', {})
                projecte_val = projecte_parcel.get('pdf_value') if isinstance(projecte_parcel, dict) else projecte_parcel
                if projecte_val is not None:
                    self._set_prefill('superficie_cadastral_m2', projecte_val, source, overall_conf)
                else:
                    # Fallback: use parcel_area_m2 from site plan
                    parcel = dims.get('parcel_area_m2', {})
                    parcel_val = parcel.get('pdf_value') if isinstance(parcel, dict) else parcel
                    if parcel_val is not None:
                        self._set_prefill('superficie_cadastral_m2', parcel_val, source, overall_conf)

            # Infer parcel_shape from plot dimensions if available
            length_info = dims.get('plot_length_m', {})
            width_info = dims.get('plot_width_m', {})
            length = length_info.get('pdf_value') if isinstance(length_info, dict) else length_info
            width = width_info.get('pdf_value') if isinstance(width_info, dict) else width_info
            if length is not None and width is not None:
                try:
                    ratio = max(float(length), float(width)) / min(float(length), float(width))
                    shape = 'quadrada' if ratio < 1.2 else 'rectangular'
                    self._user_data_full.setdefault('parcel_shape', shape)
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'  [AVÍS: error carregant {path.name}: {e}]')

    def _load_docs_intel(self) -> None:
        """Load prefills from docs_extracted.json (Phase 1.5: intelligent doc reading)."""
        path = self.project_path / 'validation' / 'docs_extracted.json'
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            fields = data.get('fields', {})
            source_base = 'docs intel'
            for field_name, field_data in fields.items():
                if not isinstance(field_data, dict):
                    continue
                value = field_data.get('value')
                confidence = field_data.get('confidence')
                field_source = field_data.get('source')
                # Only use fields with a value and sufficient confidence
                if value is None or (confidence is not None and confidence < 0.7):
                    continue
                source = f"{source_base} ({field_source})" if field_source else source_base
                self._set_prefill(field_name, value, source, confidence)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'  [AVIS: error carregant {path.name}: {e}]')

    def _load_existing_user_data(self) -> None:
        """Load from existing user_data.json -- highest priority, overrides all."""
        path = self.project_path / 'user_data.json'
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Merge: user_data values win, but keep earlier values (e.g. from planol vision)
            self._user_data_full.update(data)
            fallback_source = 'user_data.json anterior'
            saved_sources = data.get('_sources', {})
            for field in WIZARD_FIELDS:
                val = data.get(field)
                if val is not None:
                    # Override any existing prefill
                    self.prefills.pop(field, None)
                    source = saved_sources.get(field, fallback_source)
                    entry: dict = {'value': val, 'source': source}
                    self.prefills[field] = entry
            # Load expert ICGC override fields as prefills
            for field in EXPERT_ICGC_FIELDS:
                val = data.get(field)
                if val:
                    source = saved_sources.get(field, fallback_source)
                    self.prefills[field] = {'value': val, 'source': source}
            # Load expert geomech override fields as prefills
            geomech = data.get('geomech_params', {})
            if geomech:
                for field in EXPERT_GEOMECH_FIELDS:
                    val = geomech.get(field)
                    if val is not None:
                        source = saved_sources.get(f'geomech_{field}', fallback_source)
                        self.prefills[f'geomech_{field}'] = {'value': val, 'source': source}
            # Load Es_settlement override
            for field in EXPERT_SETTLEMENT_FIELDS:
                val = data.get(field)
                if val is not None:
                    source = saved_sources.get(field, fallback_source)
                    self.prefills[field] = {'value': val, 'source': source}
            # Load historia geologica template
            for field in EXPERT_HISTORIA_FIELDS:
                val = data.get(field)
                if val:
                    source = saved_sources.get(field, fallback_source)
                    self.prefills[field] = {'value': val, 'source': source}
            # Load soil_types as individual level prefills
            existing_soil_types = data.get('soil_types', [])
            for i, st in enumerate(existing_soil_types):
                field = f'soil_type_level_{i + 1}'
                source = saved_sources.get(field, fallback_source)
                self.prefills[field] = {'value': st, 'source': source}
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'  [AVÍS: error carregant {path.name}: {e}]')

    # === Template generation ===

    def _get_data_value(self, field: str):
        """Get a value from prefills or the full user_data dict, or None."""
        prefill = self.prefills.get(field)
        if prefill:
            return prefill['value']
        return self._user_data_full.get(field)

    def _generate_site_description(self) -> str:
        """Generate a default site_description from available data."""
        parts = []

        shape = self._get_data_value('parcel_shape')
        area = self._get_data_value('superficie_parcela_m2')
        if shape and area is not None:
            try:
                parts.append(
                    f"parcel\u00b7la de forma {shape} amb superf\u00edcie de {int(float(area))} m2"
                )
            except (ValueError, TypeError):
                parts.append(f"parcel\u00b7la de forma {shape}")
        elif area is not None:
            try:
                parts.append(f"parcel\u00b7la amb superf\u00edcie de {int(float(area))} m2")
            except (ValueError, TypeError):
                pass

        is_anthropized = self._get_data_value('is_anthropized')
        if is_anthropized:
            parts.append("El terreny es presenta antropitzat")

        return '. '.join(parts) if parts else ''

    def _generate_access_description(self) -> str:
        """Generate access route from the first street-facing direction.

        Returns the full sentence, e.g. "El dia dels treballs de camp es
        realitza l'entrada a la zona d'estudi a trav\u00e9s del Carrer X
        existent al sud."
        Access is always from a street, never from an adjacent parcel.
        """
        _ACCESS_PREFIX = (
            "El dia dels treballs de camp es realitza l\u2019entrada a la zona "
            "d\u2019estudi a trav\u00e9s "
        )
        STREET_ACCESS_PREPOSITIONS = {
            'carrer': 'del',
            'avinguda': "de l'",
            'cam\u00ed': 'del',
            'passatge': 'del',
            'passeig': 'del',
            'pla\u00e7a': 'de la',
            'ronda': 'de la',
            'partida': 'de la',
            'carretera': 'de la',
            'travessia': 'de la',
        }
        for direction, direction_cat in [
            ('south', 'sud'), ('north', 'nord'),
            ('east', 'est'), ('west', 'oest'),
        ]:
            field = f'adjacent_{direction}'
            val = self._get_data_value(field)
            if not val:
                continue
            val_lower = val.lower()
            for kw, prep in STREET_ACCESS_PREPOSITIONS.items():
                if kw in val_lower:
                    return f"{_ACCESS_PREFIX}{prep} {val} existent al {direction_cat}."
        return ''

    def _generate_template_prefills(self) -> None:
        """Generate prefill templates for site/access description from composite data."""
        if 'site_description' not in self.prefills:
            text = self._generate_site_description()
            if text:
                self._set_prefill('site_description', text, 'plantilla generada')
        if 'access_description' not in self.prefills:
            text = self._generate_access_description()
            if text:
                self._set_prefill('access_description', text, 'plantilla generada')

    # === Input methods ===

    def _format_source(self, prefill: dict | None) -> str:
        """Format the source line shown below a field value."""
        if not prefill:
            return '     [cap font disponible]'
        source = prefill.get('source', '')
        conf = prefill.get('confidence')
        if conf is not None:
            return f'     [font: {source} \u00b7 confian\u00e7a: {round(conf * 100)}%]'
        return f'     [font: {source}]'

    def ask_confirm(self, field: str, label: str, num: int) -> str | int | float:
        """Show pre-filled value. Enter confirms, typing overrides."""
        prefill = self.prefills.get(field)
        current = prefill['value'] if prefill else None
        display = current if current is not None else '(buit)'

        print(f'\n  {num}. {label}: {display}')
        print(self._format_source(prefill))

        if current is not None:
            raw = input('     \u2713 Confirmar [Enter] / escriu nou valor: ').strip()
        else:
            raw = input('     Valor: ').strip()

        if raw:
            # Try to preserve the type of the original value
            if isinstance(current, int):
                try:
                    return int(raw)
                except ValueError:
                    pass
            if isinstance(current, float):
                try:
                    return float(raw.replace(',', '.'))
                except ValueError:
                    pass
            return raw
        if current is not None:
            return current
        print('     [AVÍS: camp buit]')
        return ''

    def ask_input(self, field: str, label: str, num: int) -> str:
        """Free-text input. Shows prefill if available."""
        prefill = self.prefills.get(field)
        current = prefill['value'] if prefill else None
        display = current if current else '(buit)'

        print(f'\n  {num}. {label}: {display}')
        if prefill:
            print(self._format_source(prefill))
            raw = input('     \u2713 Confirmar [Enter] / escriu nou valor: ').strip()
        else:
            print('     [camp d\'observaci\u00f3]')
            raw = input('     Valor: ').strip()

        if raw:
            return raw
        return current or ''

    def ask_bool(self, field: str, label: str, num: int) -> bool:
        """Boolean input. s/Enter = yes, n = no."""
        prefill = self.prefills.get(field)
        current = prefill['value'] if prefill else True
        display = 'Si' if current else 'No'

        print(f'\n  {num}. {label}: {display}')
        print(self._format_source(prefill))

        default_hint = 'Si' if current else 'No'
        raw = input(f'     \u2713 Confirmar (s/n) [Enter={default_hint}]: ').strip().lower()

        if raw in ('n', 'no'):
            return False
        if raw in ('s', 'si', 'yes', 'y'):
            return True
        return bool(current)

    def ask_choice(
        self, field: str, label: str, options: list[str], num: int
    ) -> str:
        """Show numbered options. Number selects, Enter confirms prefill."""
        prefill = self.prefills.get(field)
        current = prefill['value'] if prefill else None

        # Try to match prefill to an option index
        preselect_idx: int | None = None
        if current:
            current_lower = current.lower()
            # First try exact match
            for i, opt in enumerate(options):
                if opt.lower() == current_lower:
                    preselect_idx = i
                    break
            # Then try keyword matching
            if preselect_idx is None:
                for keyword, canonical in _BUILDING_TYPE_KEYWORDS.items():
                    if keyword in current_lower:
                        for i, opt in enumerate(options):
                            if opt == canonical:
                                preselect_idx = i
                                break
                        break

        display = current if current else '(buit)'
        print(f'\n  {num}. {label}: {display}')
        print(self._format_source(prefill))
        print('     Opcions:')
        for i, opt in enumerate(options):
            marker = ' <--' if i == preselect_idx else ''
            print(f'       {i + 1}) {opt}{marker}')

        if preselect_idx is not None:
            raw = input(f'     Selecciona [1-{len(options)}] o Enter per confirmar: ').strip()
        else:
            raw = input(f'     Selecciona [1-{len(options)}]: ').strip()

        if raw:
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]
                print(f'     [AVÍS: número fora de rang 1-{len(options)}]')
            except ValueError:
                print(f'     [AVÍS: "{raw}" no és una opció estàndard]')
                return raw
        # Enter pressed
        if preselect_idx is not None:
            return options[preselect_idx]
        if current:
            return current
        return ''

    # === Main wizard flow ===

    def run(self) -> dict:
        """Run the interactive wizard and return the collected user_data dict."""
        expedient, municipality = self._parse_folder_name()

        print()
        print('\u2550' * 52)
        print(f'  G3DT \u2014 Wizard user_data.json')
        print(f'  Projecte: {expedient} {municipality}')
        print('\u2550' * 52)

        # Group 1: DADES DEL PROJECTE
        print(f'\n  \U0001f4cb DADES DEL PROJECTE')

        self.user_data['architect_name'] = self.ask_confirm(
            'architect_name', 'Arquitecte', 1
        )
        self.user_data['architect_company'] = self.ask_input(
            'architect_company', 'Empresa arquitecte', 2
        )
        self.user_data['building_type'] = self.ask_choice(
            'building_type', 'Tipus edificaci\u00f3', BUILDING_TYPES, 3
        )
        self.user_data['num_floors'] = self.ask_confirm(
            'num_floors', 'Plantes (ex: Pb + 1Pp, Ps + Pb + 2Pp)', 4
        )
        result_sc = self.ask_confirm(
            'superficie_construida_m2', 'Superf\u00edcie constru\u00efda (m\u00b2)', 5
        )
        try:
            self.user_data['superficie_construida_m2'] = float(
                str(result_sc).replace(',', '.')
            )
        except (ValueError, TypeError):
            self.user_data['superficie_construida_m2'] = 0.0
        self.user_data['site_description'] = self.ask_input(
            'site_description', 'Descripci\u00f3 del terreny', 6
        )
        self.user_data['access_description'] = self.ask_input(
            'access_description', "Descripci\u00f3 d'acc\u00e9s", 7
        )

        # Group 2: ADJACENTS
        print(f'\n  \U0001f4cd ADJACENTS (del visor Cadastre)')

        self.user_data['adjacent_north'] = self.ask_confirm(
            'adjacent_north', 'Nord', 8
        )
        self.user_data['adjacent_south'] = self.ask_confirm(
            'adjacent_south', 'Sud', 9
        )
        self.user_data['adjacent_east'] = self.ask_confirm(
            'adjacent_east', 'Est', 10
        )
        self.user_data['adjacent_west'] = self.ask_confirm(
            'adjacent_west', 'Oest', 11
        )

        # Group 3: PARAMETRES
        print(f'\n  \u2699\ufe0f  PAR\u00c0METRES')

        self.user_data['is_anthropized'] = self.ask_bool(
            'is_anthropized', 'Terreny antropitzat', 12
        )

        # For num_soil_levels, add extra context about detected layers
        prefill_nsl = self.prefills.get('num_soil_levels')
        if prefill_nsl and prefill_nsl.get('source', '').startswith('sondeig'):
            val = prefill_nsl['value']
            print(f'\n  13. Nivells de s\u00f2l: {val}')
            source = prefill_nsl['source']
            print(f'     [font: {source} \u00b7 {val} capes detectades]')
            raw = input('     \u2713 Confirmar [Enter] / escriu nou valor: ').strip()
            if raw:
                try:
                    self.user_data['num_soil_levels'] = int(raw)
                except ValueError:
                    self.user_data['num_soil_levels'] = val
            else:
                self.user_data['num_soil_levels'] = val
        else:
            result = self.ask_confirm('num_soil_levels', 'Nivells de s\u00f2l', 13)
            try:
                self.user_data['num_soil_levels'] = int(result)
            except (ValueError, TypeError):
                self.user_data['num_soil_levels'] = 1

        # Soil type per level (auto-detected from sondeig, Eva confirms)
        num_levels = self.user_data['num_soil_levels']
        soil_types = []

        # Load sondeig layers for description context
        sondeig_path = self.project_path / 'validation' / 'sondeig_extracted.json'
        sondeig_layers = []
        if sondeig_path.exists():
            try:
                sondeig_data = load_sondeig_json(sondeig_path)
                tests = sondeig_data.get('sondeig_tests', [])
                if tests:
                    sondeig_layers = tests[0].get('layers', [])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        SOIL_TYPE_OPTIONS = ['granular', 'arena', 'grava', 'arena_limosa', 'limo', 'arcilla', 'rock']

        for i in range(num_levels):
            # Auto-detect from sondeig description
            if i < len(sondeig_layers):
                desc = sondeig_layers[i].get('description', '')
                auto = detect_soil_type(desc)
                label = f'Tipus s\u00f2l nivell {i + 1} ({desc[:40]})'
            else:
                auto = 'granular'
                label = f'Tipus s\u00f2l nivell {i + 1}'

            field_name = f'soil_type_level_{i + 1}'
            if field_name not in self.prefills:
                self.prefills[field_name] = {'value': auto, 'source': 'auto-detecci\u00f3 descripci\u00f3'}
            result = self.ask_choice(field_name, label, SOIL_TYPE_OPTIONS, 14 + i)
            soil_types.append(result)

        self.user_data['soil_types'] = soil_types

        result_fd = self.ask_confirm(
            'foundation_depth_m', 'Profunditat fonamentaci\u00f3 (m)', 14 + num_levels
        )
        try:
            self.user_data['foundation_depth_m'] = float(
                str(result_fd).replace(',', '.')
            )
        except (ValueError, TypeError):
            self.user_data['foundation_depth_m'] = 0.3

        self.user_data['cota_referencia'] = self.ask_input(
            'cota_referencia', 'Cota refer\u00e8ncia (abs: +569.50 / rel: -4.0 / buit=ICGC)', 15 + num_levels
        )
        self.user_data['has_basement'] = self.ask_bool(
            'has_basement', 'Planta soterrani (activa \u00a74.4 empentes)', 16 + num_levels
        )
        self.user_data['has_retaining_walls'] = self.ask_bool(
            'has_retaining_walls', 'Murs de contenci\u00f3 (activa \u00a74.4 empentes)', 17 + num_levels
        )

        self.user_data['show_granulometric'] = self.ask_bool(
            'show_granulometric', 'Incloure secci\u00f3 granulom\u00e8trica (assaig contractat)', 18 + num_levels
        )

        # Group 4: EXPERT OVERRIDES (optional)
        print(f'\n  \U0001f527 OVERRIDES EXPERTS (opcional)')
        print('     Per quan la detecci\u00f3 autom\u00e0tica no \u00e9s correcta.')
        show_expert = input('     Afegir overrides? (s/n) [Enter=n]: ').strip().lower()

        if show_expert in ('s', 'si', 'y', 'yes'):
            self._run_expert_overrides()

        return self.user_data

    def _run_expert_overrides(self) -> None:
        """Run optional expert override fields for ICGC unit and geomech params."""
        # ICGC unit override (from 1:25k manual lookup)
        print(f'\n  \U0001f4d0 Unitat geol\u00f2gica ICGC (mapa 1:25.000)')
        print('     Buit = usa query WMS autom\u00e0tica (1:50.000)')
        self.user_data['icgc_unit_code'] = self.ask_input(
            'icgc_unit_code', 'Codi unitat ICGC (ex: ECbc, Tm2)', 18
        )
        if self.user_data.get('icgc_unit_code'):
            self.user_data['icgc_unit_description'] = self.ask_input(
                'icgc_unit_description', 'Descripci\u00f3 unitat', 19
            )
            self.user_data['icgc_unit_epoch'] = self.ask_input(
                'icgc_unit_epoch', '\u00c8poca (ex: Eoc\u00e8, Tri\u00e0sic)', 20
            )

        # Geomechanical parameter overrides
        print(f'\n  \u2699\ufe0f  Par\u00e0metres geomec\u00e0nics (override)')
        print('     Buit = c\u00e0lcul autom\u00e0tic CTE DB SE-C')
        self._expert_geomech = {}
        for i, (field, label, example) in enumerate([
            ('gamma', '\u03b3 densitat (g/cm\u00b3)', '2.20'),
            ('cohesion', 'c cohesi\u00f3 (kg/cm\u00b2)', '1.0'),
            ('phi', '\u03c6 angle fricci\u00f3 (\u00b0)', '35'),
            ('E', 'E m\u00f2dul deformaci\u00f3 (kg/cm\u00b2)', '500'),
        ], start=21):
            prefill = self.prefills.get(f'geomech_{field}')
            current = prefill['value'] if prefill else None
            display = current if current is not None else '(auto)'
            print(f'\n  {i}. {label}: {display}')
            if prefill:
                print(self._format_source(prefill))
            raw = input(f'     Valor (ex: {example}) o Enter per auto: ').strip()
            if raw:
                try:
                    self._expert_geomech[field] = float(raw.replace(',', '.'))
                except ValueError:
                    print(f'     [AV\u00cdS: "{raw}" no \u00e9s num\u00e8ric, ignorat]')

        # Es settlement override (Schmertmann)
        print(f'\n  \u2699\ufe0f  Es assentament Schmertmann')
        prefill = self.prefills.get('Es_settlement')
        current = prefill['value'] if prefill else None
        display = current if current is not None else '(auto: 2.5\u00d7Nb)'
        print(f'\n  25. Es assentament Schmertmann (kg/cm\u00b2): {display}')
        if prefill:
            print(self._format_source(prefill))
        raw = input('     Valor (ex: 75) o Enter per auto: ').strip()
        if raw:
            try:
                self.user_data['Es_settlement'] = float(raw.replace(',', '.'))
            except ValueError:
                print(f'     [AV\u00cdS: "{raw}" no \u00e9s num\u00e8ric, ignorat]')
        elif current is not None:
            self.user_data['Es_settlement'] = current

        # Historia geologica template override
        print(f'\n  \U0001f4dc Historia geològica (plantilla Eva)')
        prefill = self.prefills.get('historia_geologica_template')
        current = prefill['value'] if prefill else None
        display = current if current is not None else '(sense plantilla)'
        # Show just the filename for readability
        if current:
            from pathlib import Path as _P
            short = _P(current).name
            print(f'\n  26. Plantilla historia geològica: {short}')
        else:
            print(f'\n  26. Plantilla historia geològica: {display}')
        if prefill:
            print(self._format_source(prefill))
        print('     Buit = manté actual, "no" = desactiva, o escriu path alternatiu')
        raw = input('     Valor o Enter per confirmar: ').strip()
        if raw.lower() == 'no':
            self.user_data['historia_geologica_template'] = ''
        elif raw:
            self.user_data['historia_geologica_template'] = raw
        elif current:
            self.user_data['historia_geologica_template'] = current

    def save(self) -> Path:
        """Merge wizard results into user_data.json and save."""
        expert_overrides = {}
        if hasattr(self, '_expert_geomech') and self._expert_geomech:
            expert_overrides['geomech_params'] = self._expert_geomech
        if 'Es_settlement' in self.user_data:
            expert_overrides['Es_settlement'] = self.user_data.pop('Es_settlement')
        for field in EXPERT_ICGC_FIELDS:
            if field in self.user_data and self.user_data[field]:
                expert_overrides[field] = self.user_data.pop(field)

        return save_wizard_data(self.project_path, self.user_data, expert_overrides)


def save_wizard_data(
    project_path: str | Path,
    wizard_fields: dict,
    expert_overrides: dict | None = None,
    sources: dict[str, str] | None = None,
) -> Path:
    """Merge wizard fields + expert overrides into user_data.json and save.

    This is the shared save logic used by both the CLI wizard and the web API.

    Args:
        project_path: Path to the project folder.
        wizard_fields: Dict of standard wizard fields (from WIZARD_FIELDS).
        expert_overrides: Optional dict with keys like 'geomech_params',
            'Es_settlement', 'icgc_unit_code', etc.
        sources: Optional dict mapping field names to their original source
            (e.g. 'planol A.01.pdf', 'ICGC WMS 1:50k'). Persisted as _sources
            so original provenance survives save/reload cycles.

    Returns:
        Path to the saved user_data.json file.
    """
    project_path = Path(project_path)
    output_path = project_path / 'user_data.json'
    expert_overrides = expert_overrides or {}

    # Load existing file to preserve non-wizard fields
    existing: dict = {}
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, TypeError):
            existing = {}

    # Update only wizard fields
    for field in WIZARD_FIELDS:
        if field in wizard_fields:
            existing[field] = wizard_fields[field]

    # Update expert ICGC override fields
    for field in EXPERT_ICGC_FIELDS:
        val = expert_overrides.get(field)
        if val:
            existing[field] = val

    # Update expert geomech override fields
    geomech = expert_overrides.get('geomech_params')
    if geomech:
        existing.setdefault('geomech_params', {}).update(geomech)

    # Update Es_settlement (top-level, not inside geomech_params)
    if 'Es_settlement' in expert_overrides:
        existing['Es_settlement'] = expert_overrides['Es_settlement']

    # Update historia geologica template
    if 'historia_geologica_template' in wizard_fields:
        existing['historia_geologica_template'] = wizard_fields['historia_geologica_template']

    # Persist original sources so badges survive save/reload
    if sources:
        existing_sources = existing.get('_sources', {})
        existing_sources.update(sources)
        existing['_sources'] = existing_sources

    # Update metadata
    meta = existing.setdefault('_metadata', {})
    meta['generated_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    meta['wizard_used'] = True

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return output_path


def _generate_report(project_path: str, user_data_path: str) -> None:
    """Run report generator after wizard completion."""
    from .report_generator import ReportGenerator

    project = Path(project_path)
    from .folder_utils import parse_folder_name
    expedient, _ = parse_folder_name(project.name)
    output_name = f'{expedient}_generated.docx'
    output_path = project / output_name

    print(f'\n  Generant informe...')
    print(f'  Projecte: {project}')
    print(f'  User data: {user_data_path}')
    print(f'  Sortida: {output_path}')
    print()

    generator = ReportGenerator(
        project_path=str(project),
        user_data=user_data_path,
    )
    result = generator.generate(str(output_path))

    if result.warnings:
        for w in result.warnings:
            print(f'  [AVÍS] {w}')

    if result.errors:
        for e in result.errors:
            print(f'  [ERROR] {e}')

    if result.success:
        print()
        print('\u2550' * 52)
        print(f'  \u2705 Informe generat: {output_path}')
        print('\u2550' * 52)
    else:
        print()
        print('\u2550' * 52)
        print(f'  \u274c Generació fallida. Revisa els errors.')
        print('\u2550' * 52)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print('Us: python3 -m automation.wizard <project_path>')
        print('Exemple: python3 -m automation.wizard reference-material/4001612-bell-lloc')
        sys.exit(1)

    project_path = sys.argv[1]
    if not Path(project_path).exists():
        print(f'Error: no existeix el directori "{project_path}"')
        sys.exit(1)

    wizard = UserDataWizard(project_path)

    try:
        wizard.load_prefills()
        wizard.run()
        output = wizard.save()
        print()
        print('\u2550' * 52)
        print(f'  \u2705 Guardat: {output}')
        print('\u2550' * 52)

        # Offer to generate report
        print()
        generate = input('  Generar informe ara? (s/n) [Enter=s]: ').strip().lower()
        if generate in ('', 's', 'si', 'y', 'yes'):
            _generate_report(project_path, str(output))
    except KeyboardInterrupt:
        print('\n\n  Cancel\u00b7lat.')
        sys.exit(130)


if __name__ == '__main__':
    main()
