#!/usr/bin/env python3
"""
G3DT Data Entry Schema

Defineix l'esquema per a les dades que l'usuari ha d'introduir manualment
per a cada informe geotecnic. Aquestes dades NO es poden extreure automaticament
dels fitxers del projecte (DPSH Excel, noms de carpetes, etc).

Usage:
    from data_schema import DATA_ENTRY_SCHEMA, validate_data, to_json_schema

    # Validar dades d'entrada
    errors = validate_data(user_input, DATA_ENTRY_SCHEMA)

    # Exportar esquema per a formulari web
    json_schema = to_json_schema(DATA_ENTRY_SCHEMA)

Author: Eficients.cat
Date: 2026-02-03
"""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class FieldDefinition:
    """
    Defineix un camp de l'esquema de dades.

    Attributes:
        field_type: Tipus del camp ('str', 'int', 'float', 'bool', 'choice')
        required: Si el camp es obligatori
        default: Valor per defecte (None si no n'hi ha)
        options: Llista d'opcions valides per a camps 'choice'
        example: Exemple de valor valid
        description: Descripcio del camp en catala
    """
    field_type: Literal['str', 'int', 'float', 'bool', 'choice']
    required: bool = False
    default: Any = None
    options: list[str] = field(default_factory=list)
    example: str | None = None
    description: str = ""


# Opcions de tipus d'edifici
BUILDING_TYPES = [
    'Habitatge aïllat',
    'Habitatge plurifamiliar',
    'Nau industrial',
    'Edifici comercial',
    'Edifici públic',
]

# Posicions de la parcel·la
SITE_POSITIONS = ['nord', 'sud', 'est', 'oest', 'centre']

# Formes de parcel·la
PARCEL_SHAPES = ['rectangular', 'quadrada', 'irregular', 'triangular']


DATA_ENTRY_SCHEMA: dict[str, FieldDefinition] = {
    # === Informacio de l'arquitecte (del correu de pressupost) ===
    'architect_name': FieldDefinition(
        field_type='str',
        required=True,
        description="Nom de l'arquitecte o enginyer responsable del projecte",
        example="Sr. Joan Garcia"
    ),
    'architect_company': FieldDefinition(
        field_type='str',
        required=True,
        description="Empresa o despatx de l'arquitecte",
        example="Arquitectura Garcia SLP"
    ),

    # === Especificacions de l'edifici ===
    'building_type': FieldDefinition(
        field_type='choice',
        required=True,
        options=BUILDING_TYPES,
        description="Tipus de construccio prevista"
    ),
    'num_floors': FieldDefinition(
        field_type='str',
        required=True,
        example='Pb + 1Pp',
        description="Nombre de plantes (ex: Pb, Pb + 1Pp, Pb + 2Pp)"
    ),
    'superficie_parcela_m2': FieldDefinition(
        field_type='float',
        required=True,
        description="Superficie total de la parcel·la en metres quadrats",
        example="450.0"
    ),
    'superficie_construida_m2': FieldDefinition(
        field_type='float',
        required=True,
        description="Superficie construida prevista en metres quadrats",
        example="180.0"
    ),
    'has_basement': FieldDefinition(
        field_type='bool',
        required=False,
        default=False,
        description="Indica si l'edifici tindra soterrani"
    ),
    'has_retaining_walls': FieldDefinition(
        field_type='bool',
        required=False,
        default=False,
        description="Indica si es preveuen murs de contencio"
    ),

    # === Ubicacio (pot venir de consulta ICGC) ===
    'street_address': FieldDefinition(
        field_type='str',
        required=True,
        description="Adreca completa de la parcel·la",
        example="Carrer Major, 15"
    ),
    'utm_x': FieldDefinition(
        field_type='float',
        required=False,
        description="Coordenada UTM X (ETRS89 zona 31N)",
        example="297500.0"
    ),
    'utm_y': FieldDefinition(
        field_type='float',
        required=False,
        description="Coordenada UTM Y (ETRS89 zona 31N)",
        example="4615000.0"
    ),

    # === Observacions del terreny (de la visita de camp) ===
    'site_position': FieldDefinition(
        field_type='choice',
        required=False,
        options=SITE_POSITIONS,
        default='centre',
        description="Posicio de la parcel·la dins el municipi"
    ),
    'parcel_shape': FieldDefinition(
        field_type='choice',
        required=False,
        options=PARCEL_SHAPES,
        default='rectangular',
        description="Forma general de la parcel·la"
    ),
    'adjacent_north': FieldDefinition(
        field_type='str',
        required=False,
        description="Descripcio del que limita al nord",
        example="parcel·la veina amb habitatge"
    ),
    'adjacent_south': FieldDefinition(
        field_type='str',
        required=False,
        description="Descripcio del que limita al sud",
        example="carrer Major"
    ),
    'adjacent_east': FieldDefinition(
        field_type='str',
        required=False,
        description="Descripcio del que limita a l'est",
        example="parcel·la buida"
    ),
    'adjacent_west': FieldDefinition(
        field_type='str',
        required=False,
        description="Descripcio del que limita a l'oest",
        example="camp de conreu"
    ),
    'is_urban': FieldDefinition(
        field_type='bool',
        required=False,
        default=True,
        description="Indica si la parcel·la es troba en zona urbana"
    ),
    'is_sloped': FieldDefinition(
        field_type='bool',
        required=False,
        default=False,
        description="Indica si el terreny te pendent significatiu"
    ),
    'slope_percent': FieldDefinition(
        field_type='float',
        required=False,
        description="Pendent del terreny en percentatge (pre-omplert per ICGC MDT)",
        example="25.0"
    ),
    'slope_direction': FieldDefinition(
        field_type='str',
        required=False,
        description="Direccio dominant del pendent (N, NE, E, SE, S, SW, W, NW)",
        example="SE"
    ),

    # === Zona geologica (determina plantilles a usar) ===
    'geological_zone': FieldDefinition(
        field_type='choice',
        required=False,
        options=[],  # Es carrega dinamicament del servidor
        description="Zona geologica segons mapa ICGC"
    ),
    'num_soil_levels': FieldDefinition(
        field_type='int',
        required=False,
        default=1,
        description="Nombre de nivells de sol identificats"
    ),
}


class ValidationError(Exception):
    """Error de validacio d'un camp."""
    def __init__(self, field_name: str, message: str):
        self.field_name = field_name
        self.message = message
        super().__init__(f"{field_name}: {message}")


def coerce_type(value: Any, field_def: FieldDefinition) -> Any:
    """
    Converteix un valor al tipus esperat pel camp.

    Args:
        value: Valor a convertir (normalment string d'un formulari)
        field_def: Definicio del camp

    Returns:
        Valor convertit al tipus correcte

    Raises:
        ValueError: Si la conversio no es possible
    """
    if value is None or value == '':
        return field_def.default

    match field_def.field_type:
        case 'str':
            return str(value).strip()

        case 'int':
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            return int(str(value).strip())

        case 'float':
            if isinstance(value, (int, float)):
                return float(value)
            # Accepta comes com a separador decimal (catala)
            str_val = str(value).strip().replace(',', '.')
            return float(str_val)

        case 'bool':
            if isinstance(value, bool):
                return value
            str_val = str(value).strip().lower()
            if str_val in ('true', '1', 'si', 'sí', 'yes'):
                return True
            if str_val in ('false', '0', 'no'):
                return False
            raise ValueError(f"No es pot convertir '{value}' a boolean")

        case 'choice':
            str_val = str(value).strip()
            # Empty options list is intentional for dynamically populated fields
            # (e.g., geological_zone loaded from server). Any value accepted.
            if field_def.options and str_val not in field_def.options:
                raise ValueError(
                    f"Valor '{str_val}' no es valid. "
                    f"Opcions: {', '.join(field_def.options)}"
                )
            return str_val

        case _:
            return value


def validate_field(
    field_name: str,
    value: Any,
    schema: dict[str, FieldDefinition]
) -> list[str]:
    """
    Valida un camp individual.

    Args:
        field_name: Nom del camp
        value: Valor a validar
        schema: Esquema complet (per obtenir la definicio del camp)

    Returns:
        Llista d'errors (buida si valid)
    """
    errors: list[str] = []

    if field_name not in schema:
        errors.append(f"Camp desconegut: {field_name}")
        return errors

    field_def = schema[field_name]

    # Comprova si es obligatori i esta buit
    is_empty = value is None or value == ''
    if field_def.required and is_empty:
        errors.append(f"El camp '{field_name}' es obligatori")
        return errors

    # Si esta buit i no es obligatori, valid
    if is_empty:
        return errors

    # Intenta convertir i validar el tipus
    try:
        coerce_type(value, field_def)
    except (ValueError, TypeError) as e:
        errors.append(f"Error de tipus al camp '{field_name}': {e}")

    return errors


def validate_data(
    data: dict[str, Any],
    schema: dict[str, FieldDefinition] | None = None
) -> dict[str, list[str]]:
    """
    Valida totes les dades contra l'esquema.

    Args:
        data: Diccionari amb les dades a validar
        schema: Esquema a usar (per defecte DATA_ENTRY_SCHEMA)

    Returns:
        Diccionari amb errors per camp (buit si tot valid)
    """
    if schema is None:
        schema = DATA_ENTRY_SCHEMA

    all_errors: dict[str, list[str]] = {}

    # Valida camps obligatoris que falten
    for field_name, field_def in schema.items():
        if field_def.required and field_name not in data:
            all_errors.setdefault(field_name, []).append(
                f"El camp '{field_name}' es obligatori"
            )

    # Valida cada camp present
    for field_name, value in data.items():
        if field_name not in schema:
            all_errors.setdefault('_unknown', []).append(
                f"Camp desconegut: {field_name}"
            )
            continue

        field_errors = validate_field(field_name, value, schema)
        if field_errors:
            all_errors.setdefault(field_name, []).extend(field_errors)

    return all_errors


def coerce_all(
    data: dict[str, Any],
    schema: dict[str, FieldDefinition] | None = None
) -> dict[str, Any]:
    """
    Converteix tots els valors als tipus correctes.

    Args:
        data: Diccionari amb les dades originals
        schema: Esquema a usar (per defecte DATA_ENTRY_SCHEMA)

    Returns:
        Diccionari amb els valors convertits

    Raises:
        ValidationError: Si algun camp no es pot convertir
    """
    if schema is None:
        schema = DATA_ENTRY_SCHEMA

    result: dict[str, Any] = {}

    for field_name, field_def in schema.items():
        value = data.get(field_name)

        try:
            result[field_name] = coerce_type(value, field_def)
        except (ValueError, TypeError) as e:
            raise ValidationError(field_name, str(e)) from e

    return result


def to_json_schema(
    schema: dict[str, FieldDefinition] | None = None
) -> dict[str, Any]:
    """
    Converteix l'esquema a format JSON Schema per a formularis web.

    Args:
        schema: Esquema a convertir (per defecte DATA_ENTRY_SCHEMA)

    Returns:
        Diccionari compatible amb JSON Schema Draft 7
    """
    if schema is None:
        schema = DATA_ENTRY_SCHEMA

    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_name, field_def in schema.items():
        prop: dict[str, Any] = {
            'description': field_def.description,
        }

        match field_def.field_type:
            case 'str':
                prop['type'] = 'string'
            case 'int':
                prop['type'] = 'integer'
            case 'float':
                prop['type'] = 'number'
            case 'bool':
                prop['type'] = 'boolean'
            case 'choice':
                prop['type'] = 'string'
                if field_def.options:
                    prop['enum'] = field_def.options

        if field_def.default is not None:
            prop['default'] = field_def.default

        if field_def.example:
            prop['examples'] = [field_def.example]

        properties[field_name] = prop

        if field_def.required:
            required.append(field_name)

    return {
        '$schema': 'https://json-schema.org/draft-07/schema#',
        'title': 'G3DT Data Entry Schema',
        'description': 'Dades manuals per a informes geotecnics G3DT',
        'type': 'object',
        'properties': properties,
        'required': required,
        'additionalProperties': False,
    }


def get_required_fields(
    schema: dict[str, FieldDefinition] | None = None
) -> list[str]:
    """
    Retorna la llista de camps obligatoris.

    Args:
        schema: Esquema a consultar (per defecte DATA_ENTRY_SCHEMA)

    Returns:
        Llista de noms de camps obligatoris
    """
    if schema is None:
        schema = DATA_ENTRY_SCHEMA

    return [name for name, field_def in schema.items() if field_def.required]


FieldType = Literal['str', 'int', 'float', 'bool', 'choice']


def get_field_names_by_type(
    field_type: FieldType,
    schema: dict[str, FieldDefinition] | None = None
) -> list[str]:
    """
    Retorna camps d'un tipus especific.

    Args:
        field_type: Tipus de camp ('str', 'int', 'float', 'bool', 'choice')
        schema: Esquema a consultar (per defecte DATA_ENTRY_SCHEMA)

    Returns:
        Llista de noms de camps del tipus especificat
    """
    if schema is None:
        schema = DATA_ENTRY_SCHEMA

    return [
        name for name, field_def in schema.items()
        if field_def.field_type == field_type
    ]


# === CLI per a testing ===

if __name__ == '__main__':
    import json

    print("=== G3DT Data Entry Schema ===\n")

    print("Camps obligatoris:")
    for name in get_required_fields():
        print(f"  - {name}")

    print("\nCamps opcionals amb valor per defecte:")
    for name, field_def in DATA_ENTRY_SCHEMA.items():
        if not field_def.required and field_def.default is not None:
            print(f"  - {name}: {field_def.default}")

    print("\nJSON Schema:")
    print(json.dumps(to_json_schema(), indent=2, ensure_ascii=False))
