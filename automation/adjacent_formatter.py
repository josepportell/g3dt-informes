"""Format raw cadastre adjacent descriptions into Eva-style sentences."""

from __future__ import annotations

# Catalan direction names
_DIR_CAT = {'north': 'nord', 'south': 'sud', 'east': 'est', 'west': 'oest'}
# Spanish direction names
_DIR_ES = {'north': 'norte', 'south': 'sur', 'east': 'este', 'west': 'oeste'}

# Municipalities that use Spanish (Aragon + some)
_SPANISH_MUNICIPALITIES = {
    'anciles', 'benasque', 'cerler', 'graus', 'barbastro',
    'huesca', 'jaca', 'ainsa', 'campo', 'castejón de sos',
}


def _detect_language(municipality: str | None) -> str:
    """Detect language from municipality. Returns 'ca' or 'es'."""
    if not municipality:
        return 'ca'
    muni_lower = municipality.lower().strip()
    # Remove province suffix: "Anciles (Huesca)" -> "anciles"
    if '(' in muni_lower:
        muni_lower = muni_lower[:muni_lower.index('(')].strip()
    return 'es' if muni_lower in _SPANISH_MUNICIPALITIES else 'ca'


def format_adjacent(direction: str, value: str, municipality: str | None = None) -> str:
    """Format a single adjacent value into Eva-style sentence.

    Args:
        direction: 'north', 'south', 'east', or 'west'
        value: Raw cadastre value (e.g., "parcel·la buida", "Carrer X")
        municipality: For language detection (Catalan vs Spanish)

    Returns:
        Formatted sentence like "Per la part nord amb una parcel·la buida."
    """
    lang = _detect_language(municipality)

    if lang == 'es':
        return _format_adjacent_es(direction, value)
    return _format_adjacent_ca(direction, value)


def _format_adjacent_ca(direction: str, value: str) -> str:
    """Format in Catalan."""
    dir_name = _DIR_CAT.get(direction, direction)
    if not value:
        return f'Per la part {dir_name}, sense informació.'
    v = value.strip().rstrip('.')
    # Street types with masculine article "el"
    if v.lower().startswith(('carrer ', 'camí ', 'passeig ')):
        return f'Per la part {dir_name} amb el {v}.'
    # Street types with feminine article "la"
    if v.lower().startswith(('avinguda ', 'plaça ', 'ronda ', 'travessia ')):
        return f'Per la part {dir_name} amb la {v}.'
    # Feminine indefinite "una"
    if v.lower().startswith(('parcel·la', 'construcció', 'edificació', 'nau ')):
        return f'Per la part {dir_name} amb una {v}.'
    # Masculine indefinite "un"
    if v.lower().startswith(('solar', 'edifici', 'magatzem', 'terreny')):
        return f'Per la part {dir_name} amb un {v}.'
    return f'Per la part {dir_name} amb {v}.'


def _format_adjacent_es(direction: str, value: str) -> str:
    """Format in Spanish."""
    dir_name = _DIR_ES.get(direction, direction)
    if not value:
        return f'Por la parte {dir_name}, sin información.'
    v = value.strip().rstrip('.')
    # Street types with masculine article "el"
    if v.lower().startswith(('calle ', 'camino ', 'paseo ')):
        return f'Por la parte {dir_name} con el {v}.'
    # Street types with feminine article "la"
    if v.lower().startswith(('avenida ', 'plaza ', 'ronda ')):
        return f'Por la parte {dir_name} con la {v}.'
    # Feminine indefinite "una"
    if v.lower().startswith(('parcela', 'construcción', 'edificación', 'nave ', 'zona ')):
        return f'Por la parte {dir_name} con una {v}.'
    # Masculine indefinite "un"
    if v.lower().startswith(('solar', 'edificio', 'almacén', 'terreno', 'campo ', 'jardín')):
        return f'Por la parte {dir_name} con un {v}.'
    return f'Por la parte {dir_name} con {v}.'


def format_all_adjacents(
    adjacents: dict[str, str],
    municipality: str | None = None,
) -> dict[str, str]:
    """Format all 4 adjacent values into Eva-style sentences.

    Args:
        adjacents: {'north': '...', 'south': '...', 'east': '...', 'west': '...'}
        municipality: For language detection

    Returns:
        {'adjacent_north_fmt': '...', 'adjacent_south_fmt': '...', ...}
    """
    lang = _detect_language(municipality)
    result = {}

    for direction in ('north', 'south', 'east', 'west'):
        raw = adjacents.get(direction, '')
        if direction == 'west' and raw:
            # West gets special "I finalment" / "Y finalmente" prefix
            body = format_adjacent(direction, raw, municipality)
            if lang == 'es':
                # "Por la parte oeste con..." -> "Y finalmente por la parte oeste, con..."
                body = body.replace('Por la parte', 'por la parte', 1)
                result[f'adjacent_{direction}_fmt'] = f'Y finalmente {body}'
            else:
                # "Per la part oest amb..." -> "I finalment, per la part oest, amb..."
                body = body.replace('Per la part', 'per la part', 1)
                result[f'adjacent_{direction}_fmt'] = f'I finalment, {body}'
        else:
            result[f'adjacent_{direction}_fmt'] = format_adjacent(direction, raw, municipality)

    return result
