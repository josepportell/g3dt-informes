"""Format raw cadastre adjacent descriptions into Eva-style sentences (secció 2.1.1).

Peça 2 (2026-09-06, `docs/ANALISI-NARRATIVA-2026-09-06.md` §3.1): vocabulari TANCAT dels 7 signats i agrupació de costats.

- Carrer: «Per la part est amb el Carrer Mestre Ramon Ortiz.» · «Per la part nord amb el camí d'accés.»
- Buida: «Per la part nord amb una parcel·la buida.» · agrupada: «Per la part est i sud amb parcel·les buides.»
- Construïda: «amb una parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant.» ·
  «amb una parcel·la on existeix un edifici aïllat en planta baixa.» (el valor cru ve de `cadastre_adjacents._describe_neighbor`).
- Ordre nord, sud, est, oest; l'ÚLTIMA frase no buida porta «I finalment, per la part oest, amb …». Dos costats amb el
  mateix contingut (no carrer) van en UNA frase, en plural, al forat del primer; l'altre forat queda buit i la plantilla
  (`{%p if %}`) elimina el paràgraf.
- Castellà (Vilanova, Anciles): «Por la parte sur, con …», «Y finalmente, Por la parte oeste con la calle STA. GEMMA.»;
  el vocabulari català del Cadastre es tradueix (`_to_es`).
- `access_street_from_adjacents`: el forat de «…a través del {{ access_street }}.» a partir del costat que és carrer:
  «carrer adjacent situat al sud» (Castellar, Linyola) / «Carrer existent al nord» (Alcoletge) / «carrer de la Miranda»
  (Rubí) — el primer és el defecte, els altres dos candidats.
"""

from __future__ import annotations

import re
import unicodedata

# Catalan direction names
_DIR_CAT = {'north': 'nord', 'south': 'sud', 'east': 'est', 'west': 'oest'}
# Spanish direction names
_DIR_ES = {'north': 'norte', 'south': 'sur', 'east': 'este', 'west': 'oeste'}
_ORDER = ('north', 'south', 'east', 'west')

# Municipalities that use Spanish (Aragon + some)
_SPANISH_MUNICIPALITIES = {
    'anciles', 'benasque', 'cerler', 'graus', 'barbastro',
    'huesca', 'jaca', 'ainsa', 'campo', 'castejón de sos',
}

_STREET_TYPES_CA_EL = ('carrer ', 'camí ', 'passeig ', 'via ')
_STREET_TYPES_CA_LA = ('avinguda ', 'plaça ', 'ronda ', 'travessia ', 'carretera ')
_STREET_TYPES_ES_LA = ('calle ', 'avenida ', 'plaza ', 'ronda ', 'travesía ', 'carretera ')
_STREET_TYPES_ES_EL = ('camino ', 'paseo ')
_STREET_ALL = _STREET_TYPES_CA_EL + _STREET_TYPES_CA_LA + _STREET_TYPES_ES_LA + _STREET_TYPES_ES_EL + ('via pública', 'vía pública')

_NUM_CA_TO_DIGIT = {'una': '1', 'dos': '2', 'dues': '2', 'tres': '3', 'quatre': '4', 'cinc': '5', 'sis': '6',
                    'set': '7', 'vuit': '8', 'nou': '9', 'deu': '10'}


def _detect_language(municipality: str | None) -> str:
    """Detect language from municipality. Returns 'ca' or 'es'."""
    if not municipality:
        return 'ca'
    muni_lower = municipality.lower().strip()
    # Remove province suffix: "Anciles (Huesca)" -> "anciles"
    if '(' in muni_lower:
        muni_lower = muni_lower[:muni_lower.index('(')].strip()
    return 'es' if muni_lower in _SPANISH_MUNICIPALITIES else 'ca'


def is_street(value: str | None) -> bool:
    v = (value or '').strip().lower()
    return bool(v) and v.startswith(_STREET_ALL)


def _to_es(v: str) -> str:
    """Vocabulari català del Cadastre → castellà dels signats (Vilanova, Anciles)."""
    s = v.strip()
    low = s.lower()
    if low.startswith('carrer '):
        return 'calle ' + s[7:]
    if low.startswith('camí '):
        return 'camino ' + s[5:]
    if low.startswith('passeig '):
        return 'paseo ' + s[8:]
    if low.startswith('avinguda '):
        return 'avenida ' + s[9:]
    if low.startswith('plaça '):
        return 'plaza ' + s[6:]
    m = re.match(r"parcel·la amb una construcció aïllada de fins a (\w+) plantes sobre rasant(.*)$", low)
    if m:
        n = _NUM_CA_TO_DIGIT.get(m.group(1), m.group(1))
        tail = m.group(2).replace('amb soterrani', 'con sótano').replace(' i ', ' y ').replace('piscina', 'piscina')
        return f"parcela con un edificio de hasta {n} plantas sobre rasante{tail}"
    table = {
        'parcel·la buida': 'parcela sin edificaciones',
        'parcel·la veïna': 'parcela vecina',
        'parcel·la amb construcció': 'parcela con construcción',
        'parcel·la on existeix un edifici aïllat en planta baixa': 'parcela con un edificio aislado en planta baja',
        'nau industrial': 'nave industrial', 'terreny agrícola': 'campo de cultivo', 'magatzem': 'almacén',
        'via pública': 'vía pública', 'desconegut': 'desconocido', 'camí d\'accés': 'camino de acceso',
    }
    for k, val in table.items():
        if low.startswith(k):
            rest = s[len(k):].replace('amb soterrani', 'con sótano').replace(' i ', ' y ')
            return val + rest
    return s


def _pluralize_ca(v: str) -> str:
    s = v
    s = re.sub(r'^parcel·la buida', 'parcel·les buides', s)
    s = re.sub(r'^parcel·la amb una construcció', 'parcel·les amb construccions', s)
    s = re.sub(r'^parcel·la on existeix un edifici aïllat', 'parcel·les on existeixen edificis aïllats', s)
    s = re.sub(r'^parcel·la amb construcció$', 'parcel·les amb construcció', s)
    s = re.sub(r'^parcel·la veïna', 'parcel·les veïnes', s)
    return s


def _pluralize_es(v: str) -> str:
    s = v
    s = re.sub(r'^parcela sin edificaciones', 'parcelas sin edificaciones', s)
    s = re.sub(r'^parcela con un edificio', 'parcelas con edificios', s)
    s = re.sub(r'^parcela con construcción$', 'parcelas con construcción', s)
    s = re.sub(r'^parcela vecina', 'parcelas vecinas', s)
    return s


def _with_article_ca(v: str, plural: bool) -> str:
    low = v.lower()
    if low.startswith(_STREET_TYPES_CA_EL):
        return f'el {v}'
    if low.startswith(_STREET_TYPES_CA_LA):
        return f'la {v}'
    if plural:
        return _pluralize_ca(v)
    if low.startswith(('parcel·la', 'construcció', 'edificació', 'nau ', 'zona ')):
        return f'una {v}'
    if low.startswith(('solar', 'edifici', 'magatzem', 'terreny', 'camp ', 'jardí')):
        return f'un {v}'
    return v


def _with_article_es(v: str, plural: bool) -> str:
    low = v.lower()
    if low.startswith(_STREET_TYPES_ES_LA):
        return f'la {v}'
    if low.startswith(_STREET_TYPES_ES_EL):
        return f'el {v}'
    if plural:
        return _pluralize_es(v)
    if low.startswith(('parcela', 'construcción', 'edificación', 'nave ', 'zona ')):
        return f'una {v}'
    if low.startswith(('solar', 'edificio', 'almacén', 'terreno', 'campo ', 'jardín')):
        return f'un {v}'
    return v


def _head(dirs: list[str], lang: str) -> str:
    names = [(_DIR_ES if lang == 'es' else _DIR_CAT)[d] for d in dirs]
    conj = ' y ' if lang == 'es' else ' i '
    joined = names[0] if len(names) == 1 else ', '.join(names[:-1]) + conj + names[-1]   # «nord, sud i est»
    return ('Por la parte ' if lang == 'es' else 'Per la part ') + joined


def _sentence(dirs: list[str], value: str, lang: str, last: bool) -> str:
    plural = len(dirs) > 1
    if lang == 'es':
        body = _with_article_es(value, plural)
        if last:
            return f'Y finalmente, {_head(dirs, lang).replace("Por", "por", 1)}, con {body}.'
        return f'{_head(dirs, lang)}, con {body}.'
    body = _with_article_ca(value, plural)
    if last:
        return f'I finalment, {_head(dirs, lang).replace("Per", "per", 1)}, amb {body}.'
    return f'{_head(dirs, lang)} amb {body}.'


def format_adjacent(direction: str, value: str, municipality: str | None = None, lang: str | None = None) -> str:
    """Format a single adjacent value into an Eva-style sentence (no grouping, not the last one)."""
    lang = lang or _detect_language(municipality)
    v = (value or '').strip().rstrip('.')
    if not v:
        return (f'Por la parte {_DIR_ES.get(direction, direction)}, sin información.' if lang == 'es'
                else f'Per la part {_DIR_CAT.get(direction, direction)}, sense informació.')
    if lang == 'es':
        v = _to_es(v)
    return _sentence([direction], v, lang, last=False)


def format_all_adjacents(
    adjacents: dict[str, str],
    municipality: str | None = None,
    lang: str | None = None,
    fixed_sides: set[str] | None = None,
) -> dict[str, str]:
    """Format all 4 adjacent values into Eva-style sentences, grouping equal (non-street) sides.

    Returns {'adjacent_north_fmt': …, …}. A grouped side's own key is '' (the template drops the paragraph).
    Sides without value keep the «sense informació» sentence so the wizard shows the gap. `fixed_sides` (sentences
    written by Eva or the synthesis) are never grouped and count as non-empty when deciding the last sentence.
    """
    lang = lang or _detect_language(municipality)
    fixed = set(fixed_sides or ())
    vals = {d: (adjacents.get(d) or '').strip().rstrip('.') for d in _ORDER}
    if lang == 'es':
        vals = {d: (_to_es(v) if v else v) for d, v in vals.items()}

    groups: list[tuple[list[str], str]] = []
    used: set[str] = set()
    for d in _ORDER:
        if d in used:
            continue
        v = vals[d]
        same = [e for e in _ORDER if e not in used and e not in fixed and v and vals[e] == v and not is_street(v)]
        if d not in fixed and len(same) >= 2:
            groups.append((same, v))
            used.update(same)
        else:
            groups.append(([d], v))
            used.add(d)

    result = {f'adjacent_{d}_fmt': '' for d in _ORDER}
    filled = [g for g in groups if g[1] or g[0][0] in fixed]
    for i, (dirs, v) in enumerate(filled):
        if dirs[0] in fixed:
            continue
        result[f'adjacent_{dirs[0]}_fmt'] = _sentence(dirs, v, lang, last=(i == len(filled) - 1))
    for dirs, v in groups:
        if not v and dirs[0] not in fixed:
            result[f'adjacent_{dirs[0]}_fmt'] = format_adjacent(dirs[0], '', municipality, lang)
    return result


# Sources in user_data._sources[key] that override format_all_adjacents output.
# Ordered most-trusted first for documentation purposes only (string match).
_TRUSTED_FMT_SOURCES = ('user', 'llm_synthesis_with_observations')


def resolve_adjacent_fmt(
    adjacents: dict[str, str],
    user_data: dict,
    municipality: str | None = None,
    lang: str | None = None,
) -> dict[str, str]:
    """Resolve the 4 `adjacent_*_fmt` sentences with trusted-source precedence.

    Precedence per direction:
      1. `user_data['adjacent_{dir}_fmt']` when its source in
         `user_data['_sources']` is 'user' or 'llm_synthesis_with_observations'.
      2. `format_all_adjacents(adjacents, municipality)` (cadastre template).

    Returns a dict with all 4 `adjacent_{dir}_fmt` keys populated.
    """
    ud_sources = (user_data.get('_sources') or {}) if isinstance(user_data, dict) else {}
    fixed = {d for d in _ORDER
             if isinstance(user_data, dict) and user_data.get(f'adjacent_{d}_fmt')
             and (ud_sources.get(f'adjacent_{d}_fmt', '') if isinstance(ud_sources, dict) else '') in _TRUSTED_FMT_SOURCES}
    adj_formatted = format_all_adjacents(adjacents, municipality, lang, fixed_sides=fixed)
    resolved: dict[str, str] = {}
    for direction in _ORDER:
        key = f'adjacent_{direction}_fmt'
        ud_val = user_data.get(key) if isinstance(user_data, dict) else None
        ud_src = ud_sources.get(key, '') if isinstance(ud_sources, dict) else ''
        if ud_val and ud_src in _TRUSTED_FMT_SOURCES:
            resolved[key] = str(ud_val)
        else:
            resolved[key] = adj_formatted.get(key, '')
    return resolved


# --- Carrer d'accés -----------------------------------------------------------------------------------------------

def _norm_street(name: str) -> str:
    """Nom de via comparable: sense accents, sense tipus ni partícules («Carrer dels Arbrells» ≡ «carrer Arbrells»)."""
    s = unicodedata.normalize('NFD', (name or '').lower())
    s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    s = re.sub(r"\bc/\s*", ' ', s)
    s = re.sub(r"\b(carrer|c\.|calle|cl|cami|camino|avinguda|avenida|av\.|placa|plaza|passeig|paseo|ronda|via|travessia)\b\.?", ' ', s)
    s = re.sub(r"\b(de|del|dels|d'|la|el|les|els|los|las|l')\b", ' ', s)
    s = re.sub(r"[^a-z0-9 ]", ' ', s)
    return ' '.join(s.split())


def access_street_from_adjacents(adjacents: dict[str, str], address_street: str | None = None,
                                 lang: str = 'ca') -> tuple[str, list[str]]:
    """(defecte, candidats) del forat «a través del {{ access_street }}.» a partir dels costats que són carrer.

    Costat: el que coincideix amb la via de l'adreça; si no, el primer carrer en l'ordre nord, sud, est, oest. Formes de
    l'Eva: «carrer adjacent situat al sud» (defecte, 2/4), «Carrer existent al nord», «carrer de la Miranda» (nom).
    Sense cap costat carrer: ('', [])."""
    streets = {d: adjacents.get(d, '') for d in _ORDER if is_street(adjacents.get(d))}
    if not streets:
        # Cap costat carrer al Cadastre (Alcoletge: camí privat d'urbanització) → el nom de la via de l'adreça llegida,
        # forma «carrer de la Miranda» (Rubí); res d'inventar-hi un costat (peça 3, 2026-09-07).
        name = re.sub(r"(?i)^(situat\s+|situada\s+)?entre\s+(.+?)\s+(?:i|y)\s+.*$", r"\2", (address_street or '').strip())
        name = re.sub(r",.*$", "", name).strip().rstrip('.')
        name = re.sub(r"(?i)^(el|la|els|les|l')\s*", "", name).strip()    # «el carrer Antoni Bellet» → «carrer Antoni Bellet»
        name = re.sub(r"\s+\d+\s*[A-Za-z]?$", "", name).strip()          # «Carrer Nou 14» → «Carrer Nou»
        if not name or not re.match(r"(?i)^(carrer|c/|c\.|camí|cami|passeig|avinguda|av\.|plaça|ronda|travessia|calle|camino|paseo|avenida|plaza)\b", name):
            return '', []
        named = name[0].lower() + name[1:] if lang != 'es' or name.lower().startswith(('calle', 'camino', 'paseo', 'avenida', 'plaza')) else name
        return named, [named]
    side = None
    if address_street:
        m = re.match(r"(?i)^\s*(?:situat\s+|situada\s+)?entre\s+(.+?)\s+(?:i|y)\s+", address_street)
        key = _norm_street(m.group(1) if m else address_street)     # «entre X i Y» → X (Bell-lloc: el sud)
        for d, v in streets.items():
            if key and (_norm_street(v) == key or key in _norm_street(v) or _norm_street(v) in key):
                side = d
                break
    if side is None:
        side = next(iter(streets))
    name = streets[side].strip().rstrip('.')
    if lang == 'es':
        d = _DIR_ES[side]
        low = name.lower()
        named = name[0].lower() + name[1:] if low.startswith(('calle', 'camino', 'paseo', 'avenida', 'plaza')) else name
        default = f'calle situada al {d}'
        return default, [default, named, f'calle existente al {d}']
    d = _DIR_CAT[side]
    low = name.lower()
    named = name[0].lower() + name[1:] if low.startswith(('carrer', 'camí', 'passeig', 'avinguda', 'plaça')) else name
    default = f'carrer adjacent situat al {d}'
    cands = [default, f'Carrer existent al {d}']
    if named and named.lower() != 'via pública':
        cands.append(named)
    return default, cands
