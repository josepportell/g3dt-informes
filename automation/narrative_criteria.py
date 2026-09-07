"""Narrativa per CRITERI (peça 1, 2026-09-06 nit): les frases fixes de l'Eva amb els seus forats, decidits per criteri.

`docs/ANALISI-NARRATIVA-2026-09-06.md` §4: els textos de l'informe NO són redacció lliure. Als 7 signats són fórmules
literals (idèntiques als 5 en català, i amb l'equivalent castellà als 2 en castellà) amb un o dos forats que es decideixen
per criteri: nombre de nivells, classe d'agressivitat, zona de radó, estat del solar (pendent / antropitzat), plantes i
soterrani, nivell més desfavorable. Es modelen com l'assentament (`settlement_criteria.py`): frase per criteri + candidats
amb procedència quan l'Eva tria (estat del solar, estructura), mai un LLM escrivint prosa.

Fórmules (literal dels signats; les errates de l'Eva no es reprodueixen: «un sòl nivel», «del murs», «més desfavorables»):

- `materials_intro`  (5/5 CA, 2/2 ES)   «A partir dels assaigs in situ realitzats, s'ha establert {un sòl nivell | dos
  nivells} de materials des del punt de vista geològic - geotècnic: (veure annex “Registre assaigs mecànics”):»
- `conclusions_levels_detected` (5/5 CA) «Es detecta {un sòl nivell | dos nivells} de materials des del punt de vista
  geològic/geotècnic en el subsòl del solar en estudi.»  (ES: «A partir de los ensayos realizados se puede describir en
  el solar en estudio dos niveles de materiales…», 2/2)
- `conclusions_aggressivity_statement` (4/5 CA; Bell-lloc porta «xxxx», el forat que l'Eva no va omplir) «A partir dels
  resultats dels assaigs de laboratori realitzats, els materials del subsòl on es preveu armar la fonamentació, a priori,
  es presenten NO AGRESSIUS al formigó.»
- `radon_sentence` (nou forat únic del paràgraf, 7/7) «La parcel·la concreta d'estudi es localitza al terme municipal
  {de | d'}{MUNICIPI} i, segons la taula existent a l'apèndix B del RD 732/2019, {pertany a la ZONA 1. | pertany a la
  ZONA 2. | no pertany a cap municipi amb concentracions inadequades de gas radó en edificis tancats.}» (Linyola = zona 0)
- `site_condition` (frase sencera; abans la plantilla en fixava la capçalera «Degut a que…» i el forat era «pla»):
  «{Com que es tracta d'un solar pla | Tot i no ser un solar pla | Degut a que es tracta d'un solar antropitzat | Es tracta
  d'un solar no antropitzat}, no s'han detectat marques i/o indicis de processos d'erosió relacionats amb l'escolament
  hídric superficial, ni es preveu que apareguin.»  Criteri (el del wizard, 2026-04): pendent > 10 % → «Tot i no ser un
  solar pla»; antropitzat → «Degut a que…»; pendent i explícitament no antropitzat → «Es tracta d'un solar no
  antropitzat»; si no → «Com que es tracta d'un solar pla». Les altres tres, candidats.
- `building_structure_desc` (clàusula sencera després de «…construcció d'una estructura »): (a) «en planta baixa[ i porxo],
  i per tant, no es preveu cap excavació important, únicament l'excavació pel sanejament, anivellació, i per a la
  implantació dels elements de fonamentació.» (Rubí, Bell-lloc) · (b) «sense nivell de soterrani, i per tant, únicament es
  preveu el sanejament, anivellació, i l'excavació fins a la cota de fonamentació.» (Castellar, Linyola, Alcoletge) ·
  (c) soterrani (cap signat CA; Anciles ES és text lliure). L'Eva NO tria (a)/(b) per plantes (Linyola PB → b; Bell-lloc
  Pb+1Pp → a): defecte = (a) si només planta baixa, (b) si té pis i no soterrani, (c) si soterrani; l'altra, candidat.
  Pregunta 18 a l'Eva.
- `empentes_paragraph` (Castellar CA, Anciles ES) «Pel dimensionament dels murs que es projectin i pel càlcul de les
  empentes de terres caldrà tenir en compte els paràmetres geomecànics dels materials del {1er} nivell que es considera
  el més desfavorable. Cal tenir en compte que en el trasdós del mur, caldrà instal·lar un correcte drenatge per a evitar
  que s'acumuli aigua i es produeixi una sobrecàrrega en el seu trasdós.»  Nivell = el de φ més baix (i c més baixa).
- `csn_radon_text`: el paràgraf del CSN ja és text fix de la plantilla (p474): SEMPRE buit (abans s'imprimia dues vegades).

Idioma: `language_for(municipality, *texts)` → «ca» | «es» (municipis aragonesos coneguts o marcadors castellans a les
dades llegides). Cap crida externa; pur.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# --- Idioma -----------------------------------------------------------------------------------------------------

#: Municipis on l'informe es fa en castellà (Aragó). Vilanova de Segrià (2026) també es va fer en castellà: l'idioma el
#: tria el client, per això també mirem marcadors a les dades llegides.
ES_MUNICIPALITIES = frozenset({
    "anciles", "benasque", "cerler", "graus", "barbastro", "huesca", "jaca", "ainsa", "campo", "castejón de sos",
})
ES_MARKERS = ("vivienda", "ensayo", "calle ", "sótano", "planta baja", "semisótano", "edificio", "parcela ")


def language_for_report(data: Any, user_data: dict | None = None) -> str:
    """Idioma de l'informe: `report_language` (user_data o `ReportData`) si l'Eva l'ha fixat; si no, `language_for`."""
    forced = ((user_data or {}).get("report_language") or getattr(data, "report_language", "") or "").strip().lower()
    if forced in ("ca", "es"):
        return forced
    return language_for(getattr(data, "municipality", None), getattr(data, "building_type", None),
                        getattr(data, "street_address", None))


def language_for(municipality: str | None, *texts: str | None) -> str:
    """«es» si el municipi és de la llista castellana o si les dades llegides porten marcadors castellans; si no «ca»."""
    muni = (municipality or "").lower().strip()
    if "(" in muni:
        muni = muni[:muni.index("(")].strip()
    if muni in ES_MUNICIPALITIES:
        return "es"
    sample = " ".join(str(t) for t in texts if t).lower()
    return "es" if any(m in sample for m in ES_MARKERS) else "ca"


# --- Candidats --------------------------------------------------------------------------------------------------

@dataclass
class Candidate:
    value: str
    source: str


@dataclass
class NarrativeChoice:
    value: str                      # el que s'imprimeix (defecte)
    source: str                     # per què (criteri aplicat)
    candidates: list[Candidate] = field(default_factory=list)   # [defecte, alternatives…]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def alternatives(self) -> list[str]:
        return [c.value for c in self.candidates if c.value != self.value]


# --- Nombres i ordinals -----------------------------------------------------------------------------------------

_LEVELS_CA = {1: "un sol nivell", 2: "dos nivells", 3: "tres nivells", 4: "quatre nivells", 5: "cinc nivells"}
_LEVELS_ES = {1: "un solo nivel", 2: "dos niveles", 3: "tres niveles", 4: "cuatro niveles", 5: "cinco niveles"}
_ORD_CA = {1: "1er", 2: "2on", 3: "3er", 4: "4t", 5: "5è"}
_ORD_ES_SHORT = {1: "1er", 2: "2do", 3: "3er", 4: "4to", 5: "5to"}
_ORD_ES_WORD = {1: "primer", 2: "segundo", 3: "tercer", 4: "cuarto", 5: "quinto"}


def levels_phrase(n: int, lang: str = "ca") -> str:
    n = max(1, int(n or 1))
    table = _LEVELS_ES if lang == "es" else _LEVELS_CA
    return table.get(n, f"{n} {'niveles' if lang == 'es' else 'nivells'}")


def ordinal(n: int, lang: str = "ca", word: bool = False) -> str:
    n = max(1, int(n or 1))
    if lang == "es":
        return (_ORD_ES_WORD if word else _ORD_ES_SHORT).get(n, f"{n}º")
    return _ORD_CA.get(n, f"{n}è")


# --- Municipi ---------------------------------------------------------------------------------------------------

def municipality_upper(municipality: str | None) -> str:
    """Nom oficial en majúscules (padró INE si hi és: «CASTELLAR DEL VALLÈS», «BELL-LLOC D'URGELL»); si no, el text net."""
    raw = re.sub(r"\s*\(.*?\)\s*$", "", (municipality or "").strip())
    if not raw:
        return ""
    try:
        from .municipis import lookup
        hit = lookup(raw) or lookup(raw.replace(".", "-"))
        if hit is not None:
            return hit.name_ine.upper()
    except Exception:  # padró no disponible: el text net
        pass
    return re.sub(r"\s+", " ", raw).upper()


def municipality_proper(municipality: str | None) -> str:
    """Nom oficial del padró («Bell-lloc d'Urgell», «Castellar del Vallès»); si no hi és, el text net tal qual."""
    raw = re.sub(r"\s*\(.*?\)\s*$", "", (municipality or "").strip())
    if not raw:
        return ""
    try:
        from .municipis import lookup
        hit = lookup(raw) or lookup(raw.replace(".", "-"))
        if hit is not None:
            return hit.name_ine
    except Exception:
        pass
    return re.sub(r"\s+", " ", raw)


def location_sentence_from_streets(street_1: str | None, second_street: str | None, municipality: str | None,
                                   lang: str = "ca") -> str:
    """Forat de «L'edificació que es preveu construir es situarà {{ location_sentence }}.» (Bell-lloc, l'únic signat
    que la porta: «entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell»).

    - Adreça llegida que ja diu «(Situat) entre X i Y» → tal qual, amb «Carrer» en majúscula i el municipi del padró.
    - Dos carrers diferents (nom normalitzat) → «entre el Carrer X i el Carrer Y de Municipi».
    - Un carrer → «al Carrer X de Municipi»; cap → «al terme municipal de Municipi»."""
    from .adjacent_formatter import _norm_street
    muni = municipality_proper(municipality)
    de_muni = de_municipality(muni) if muni else ""          # «de Rubí» / «d'Alcoletge»
    suffix = (f" {de_muni}" if muni else "")
    s1 = (street_1 or "").strip().rstrip(".")
    s2 = (second_street or "").strip().rstrip(".")
    if re.match(r"(?i)^(situat\s+|situada\s+)?entre\s+", s1):
        phrase = re.sub(r"(?i)^(situat|situada)\s+", "", s1)
        phrase = re.sub(r"(?i)\bcarrer\b", "Carrer", phrase)
        return f"{phrase}{suffix}"
    if s2 and _norm_street(s2) == _norm_street(s1):
        s2 = ""

    def _art(name: str) -> str:
        low = name.lower()
        if low.startswith(("avinguda", "autopista")):
            return "l'"
        if low.startswith(("plaça", "ronda", "travessia", "partida", "carretera")):
            return "la "
        return "el "

    def _cap(name: str) -> str:
        return re.sub(r"(?i)^(carrer|camí|avinguda|plaça|passeig)\b", lambda m: m.group(1).capitalize(), name)

    if s1 and s2:
        return f"entre {_art(s1)}{_cap(s1)} i {_art(s2)}{_cap(s2)}{suffix}"
    if s1:
        art = _art(s1)
        prep = "a l'" if art == "l'" else ("a la " if art == "la " else "al ")
        return f"{prep}{_cap(s1)}{suffix}"
    if muni:
        return f"al terme municipal {de_muni}"
    return "en una ubicació no especificada"


def de_municipality(municipality_upper_name: str) -> str:
    """«de CASTELLAR DEL VALLÈS» / «d'ALCOLETGE» (apòstrof davant de vocal o H)."""
    name = municipality_upper_name.strip()
    if name and name[0].upper() in "AEIOUÀÁÈÉÍÏÒÓÚÜH":
        return f"d'{name}"
    return f"de {name}"


def municipality_de(municipality: str | None) -> str:
    """Forat «en el municipi {{ municipality_de }}» (bloc 2, 2026-09-07): «d'Alcoletge» (signat), «de Rubí»,
    «de Bell-lloc d'Urgell». Abans la plantilla tenia «de » fix i imprimia «de Alcoletge». Buit → «»."""
    muni = municipality_proper(municipality)
    return de_municipality(muni) if muni else ""


# --- Tipus d'edificació amb article (bloc 2, 2026-09-07) -------------------------------------------------------
# Als signats el forat és el text DESPRÉS de «…es preveu la construcció »: «d'un habitatge unifamiliar aïllat modular»
# (Rubí), «d'un habitatge unifamiliar» (Bell-lloc), «d'un nou habitatge unifamiliar» (Linyola), «de 3 habitatges
# unifamiliars d'estructura lleugera, fusta» (Castellar), «de l'ampliació d'un edifici en planta baixa» (Alcoletge),
# ES «de una vivienda unifamiliar aislada», «de 7 viviendas unifamiliares adosadas». La plantilla tenia «d'un» FIX:
# ara el forat és `{{ building_type_de }}` i l'article surt del gènere/nombre del cap del sintagma llegit.
_FEM_HEADS = frozenset({
    "casa", "caseta", "nau", "nave", "vivenda", "vivienda", "planta", "piscina", "pergola", "torre", "masia", "granja",
    "fabrica", "escola", "escuela", "llar", "residencia", "estacio", "estacion", "promocio", "promocion", "estructura",
    "coberta", "cubierta", "terrassa", "terraza", "bassa", "balsa", "reforma", "obra", "cabana", "cabaña", "borda",
    "ampliacio", "ampliacion", "rehabilitacio", "rehabilitacion", "construccio", "construccion", "instal·lacio",
    "instalacion", "urbanitzacio", "urbanizacion", "legalitzacio", "legalizacion", "adequacio", "adecuacion",
    "consolidacio", "consolidacion", "substitucio", "sustitucion", "reparacio", "reparacion", "demolicio", "demolicion",
})
_INTERVENTION_HEADS = frozenset({
    "ampliacio", "ampliacion", "reforma", "rehabilitacio", "rehabilitacion", "tancament", "cerramiento", "canvi", "cambio",
    "substitucio", "sustitucion", "enderroc", "derribo", "demolicio", "demolicion", "legalitzacio", "legalizacion",
    "adequacio", "adecuacion", "consolidacio", "consolidacion", "reparacio", "reparacion", "instal·lacio", "instalacion",
    "urbanitzacio", "urbanizacion", "construccio", "construccion", "reconstruccio", "reconstruccion", "condicionament",
    "acondicionamiento", "reforç", "refuerzo", "adequacio",
})
_NUMBER_START_RE = re.compile(r"^(\d+|dos|dues|tres|quatre|cuatro|cinc|cinco|sis|seis|set|siete|vuit|ocho|nou|nueve|deu|diez)\b")
_ARTICLE_START_RE = re.compile(r"^(un|una|uns|unes|unos|unas|el|la|els|les|los|las)\s|^l'")


def _strip_accents_lower(s: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn").lower()


def building_type_with_article(building_type: str | None, lang: str = "ca") -> str:
    """«habitatge unifamiliar aïllat» → «un habitatge unifamiliar aïllat»; «3 habitatges…» → tal qual; «ampliació
    d'habitatge» → «l'ampliació d'habitatge»; «tancament de porxo…» → «el tancament de porxo…»; ES «vivienda…» →
    «una vivienda…». Un text que ja porta article o número surt tal qual; buit → «»."""
    t = re.sub(r"\s+", " ", (building_type or "").strip())
    if not t:
        return ""
    low = _strip_accents_lower(t)
    if _NUMBER_START_RE.match(low) or _ARTICLE_START_RE.match(low):
        return t
    head = re.sub(r"[^\w·]", "", low.split()[0])
    fem = head in _FEM_HEADS or head.endswith(("cio", "cion", "sio", "sion", "tat", "dad"))
    vowel = low[0] in "aeiouh"
    if head in _INTERVENTION_HEADS:
        if lang == "ca" and vowel:
            return f"l'{t}"
        return ("la " if fem else "el ") + t
    return ("una " if fem else "un ") + t


def de_building_type(building_type: str | None, lang: str = "ca") -> str:
    """Forat «…es preveu la construcció {{ building_type_de }}.»: «d'un habitatge unifamiliar aïllat», «de 3 habitatges
    …», «de l'ampliació …», «del tancament …»; ES «de una vivienda …», «de 7 viviendas …». Buit → «»."""
    form = building_type_with_article(building_type, lang)
    if not form:
        return ""
    low = _strip_accents_lower(form)
    if lang == "ca":
        if low.startswith(("un ", "una ", "uns ", "unes ")):
            return f"d'{form}"
        if low.startswith("el "):
            return "del " + form[3:]
        if low.startswith("els "):
            return "dels " + form[4:]
        return f"de {form}"
    if low.startswith("el "):
        return "del " + form[3:]
    return f"de {form}"


# --- Fórmules ---------------------------------------------------------------------------------------------------

def materials_intro(num_levels: int, lang: str = "ca") -> str:
    if lang == "es":
        return (f"A partir de todos los ensayos realizados en el solar, se puede describir {levels_phrase(num_levels, 'es')} "
                "de materiales des del punto de vista geológico/geotécnico en el subsuelo del solar: "
                "(ver anexo “Registro ensayos mecánicos”)")
    return (f"A partir dels assaigs in situ realitzats, s'ha establert {levels_phrase(num_levels)} de materials des del "
            "punt de vista geològic - geotècnic: (veure annex “Registre assaigs mecànics”):")


def levels_detected(num_levels: int, lang: str = "ca") -> str:
    if lang == "es":
        return (f"A partir de los ensayos realizados se puede describir en el solar en estudio {levels_phrase(num_levels, 'es')} "
                "de materiales des del punto de vista geológico/geotécnico en el subsuelo.")
    return (f"Es detecta {levels_phrase(num_levels)} de materials des del punt de vista geològic/geotècnic en el subsòl "
            "del solar en estudi.")


_AGG_CA = {"Qa": "NO AGRESSIUS", "Qb": "AGRESSIUS (agressivitat FEBLE)", "Qc": "AGRESSIUS (agressivitat MITJANA)",
           "Qd": "AGRESSIUS (agressivitat FORTA)"}
_AGG_ES = {"Qa": "NO AGRESIVOS", "Qb": "AGRESIVOS (agresividad DÉBIL)", "Qc": "AGRESIVOS (agresividad MEDIA)",
           "Qd": "AGRESIVOS (agresividad FUERTE)"}


def aggressivity_sentence(agg_class: str | None, lang: str = "ca", level_number: int | None = None) -> str:
    """Classe CE-21 (Qa no agressiu, Qb feble, Qc mitjana, Qd forta) → frase de conclusions. `None`/«» → sense laboratori.

    Només NO AGRESSIUS té exemple signat (4 CA + Anciles ES amb el forat «xxxxxxx»); les altres classes segueixen la mateixa
    fórmula amb la classe entre parèntesis.
    """
    cls = (agg_class or "").strip()
    if not cls:
        if lang == "es":
            return "No se han realizado ensayos de laboratorio para determinar la agresividad de los materiales del subsuelo al hormigón."
        return "No s'han realitzat assaigs de laboratori per determinar l'agressivitat dels materials del subsòl al formigó."
    if lang == "es":
        word = _AGG_ES.get(cls, cls)
        lvl = f"del {ordinal(level_number, 'es')} nivel descrito" if level_number else "del subsuelo donde se prevé armar la cimentación"
        return f"A partir de los ensayos realizados se determina que los materiales {lvl} se presentan, a priori {word} al hormigón."
    word = _AGG_CA.get(cls, cls)
    return ("A partir dels resultats dels assaigs de laboratori realitzats, els materials del subsòl on es preveu armar la "
            f"fonamentació, a priori, es presenten {word} al formigó.")


def aggressivity_class_from_sulfate(sulfate_mg_kg: float | None) -> str:
    """EHE-08 / CE-21 pel contingut en sulfats (mg/kg): < 2000 Qa, < 3000 Qb, < 12000 Qc, si no Qd."""
    if sulfate_mg_kg is None:
        return ""
    if sulfate_mg_kg < 2000:
        return "Qa"
    if sulfate_mg_kg < 3000:
        return "Qb"
    if sulfate_mg_kg < 12000:
        return "Qc"
    return "Qd"


def radon_sentence(zone: int | str | None, municipality: str | None, lang: str = "ca") -> NarrativeChoice:
    """Frase sencera del radó (paràgraf de la plantilla `{{ radon_sentence }}`). Zona 0 → «no pertany a cap municipi…»."""
    try:
        z = int(str(zone).strip()) if zone not in (None, "") else 1
    except ValueError:
        z = 1
    muni = municipality_upper(municipality)
    if lang == "es":
        head = (f"La parcela concreta de estudio se localiza en el término municipal de {muni} y, según la tabla existente "
                "en el apéndice B del RD 732/2019, ")
        if z <= 0:
            tail = "no pertenece a ningún municipio con concentraciones inadecuadas de gas radón en el interior de los locales habitables."
            notes = ["zona 0 en castellà: sense exemple signat"]
        elif z == 1:
            tail = ("pertenece a Municipios ZONA 1, con concentraciones inadecuadas de Gas Radón procedente del terreno en el "
                    "interior de los locales habitables.")
            notes = []
        else:
            tail = f"pertenece a ZONA {z}."
            notes = []
        return NarrativeChoice(head + tail, f"zona {z} (RD 732/2019, apèndix B)", [Candidate(head + tail, "signat ES")], notes)
    head = (f"La parcel·la concreta d'estudi es localitza al terme municipal {de_municipality(muni)} i, segons la taula "
            "existent a l'apèndix B del RD 732/2019, ")
    if z <= 0:
        main = head + "no pertany a cap municipi amb concentracions inadequades de gas radó en edificis tancats."
        return NarrativeChoice(main, "zona 0 (Linyola)", [Candidate(main, "signat: Linyola")])
    main = head + f"pertany a la ZONA {z}."
    cands = [Candidate(main, "signat: Castellar, Bell-lloc, Alcoletge")]
    if z == 1:
        cands.append(Candidate(head + "pertany a la ZONA 1, municipi amb concentracions inadequades de gas radó en edificis tancats.",
                               "signat: Rubí"))
    return NarrativeChoice(main, f"zona {z} (RD 732/2019, apèndix B)", cands)


SITE_CONDITION_TAIL_CA = (", no s'han detectat marques i/o indicis de processos d'erosió relacionats amb l'escolament hídric "
                          "superficial, ni es preveu que apareguin.")
SITE_CONDITION_ES = ("En la zona de estudio no se han detectado marcas de inicios de procesos de erosión relacionados con la "
                     "escorrentía hídrica superficial.")
_SITE_HEADS_CA = {
    "pla": "Com que es tracta d'un solar pla",
    "pendent": "Tot i no ser un solar pla",
    "antropitzat": "Degut a que es tracta d'un solar antropitzat",
    "no_antropitzat": "Es tracta d'un solar no antropitzat",
}
SLOPE_THRESHOLD_PCT = 10.0


def _to_bool(v: Any) -> bool | None:
    if v is None or (isinstance(v, str) and v.strip().lower() in ("", "none")):
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("false", "0", "no")


def site_condition_sentence(slope_percent: Any = None, is_anthropized: Any = None, lang: str = "ca") -> NarrativeChoice:
    """Frase sencera de l'estat del solar (3.3.1 i 4.2). Criteri del wizard (2026-04) + els altres caps com a candidats."""
    if lang == "es":
        return NarrativeChoice(SITE_CONDITION_ES, "fórmula única en castellà (Vilanova, Anciles)",
                               [Candidate(SITE_CONDITION_ES, "signat ES")])
    try:
        slope = float(slope_percent) if slope_percent not in (None, "") else 0.0
    except (TypeError, ValueError):
        slope = 0.0
    anthro = _to_bool(is_anthropized)
    sloped = slope > SLOPE_THRESHOLD_PCT
    if sloped and anthro is False:
        key, why = "no_antropitzat", f"pendent {slope:.0f} % i no antropitzat (Rubí)"
    elif sloped:
        key, why = "pendent", f"pendent {slope:.0f} % > {SLOPE_THRESHOLD_PCT:.0f} % (Castellar)"
    elif anthro:
        key, why = "antropitzat", "solar antropitzat (Bell-lloc)"
    else:
        key, why = "pla", f"pendent {slope:.0f} % ≤ {SLOPE_THRESHOLD_PCT:.0f} %, no antropitzat (Linyola, Alcoletge)"
    order = [key] + [k for k in ("pla", "pendent", "antropitzat", "no_antropitzat") if k != key]
    cands = [Candidate(_SITE_HEADS_CA[k] + SITE_CONDITION_TAIL_CA, f"cap «{_SITE_HEADS_CA[k]}»") for k in order]
    notes = [] if anthro is not None else ["antropitzat sense font (no derivable del Cadastre ni de l'ICGC): revisar"]
    return NarrativeChoice(cands[0].value, why, cands, notes)


_STRUCT_CA = {
    "pb": ("en planta baixa{porxo}, i per tant, no es preveu cap excavació important, únicament l'excavació pel sanejament, "
           "anivellació, i per a la implantació dels elements de fonamentació."),
    "sense_soterrani": ("sense nivell de soterrani, i per tant, únicament es preveu el sanejament, anivellació, i l'excavació "
                        "fins a la cota de fonamentació."),
    "soterrani": ("amb nivell de soterrani, i per tant, es preveu una excavació general fins a la cota de fonamentació del "
                  "soterrani, a més del sanejament i l'anivellació."),
}
_STRUCT_ES = {
    "pb": ("de planta baja{porxo}, y por tanto no se prevé ninguna excavación importante, únicamente la excavación para el "
           "saneamiento, la nivelación y para la implantación de los elementos de cimentación."),
    "sense_soterrani": ("sin nivel de sótano, y por tanto, únicamente se prevé el saneamiento, nivelación y la excavación hasta "
                        "la cota de cimentación."),
    "soterrani": ("con nivel de sótano, y por tanto se prevé una excavación general hasta la cota de cimentación del sótano, "
                  "además del saneamiento y la nivelación."),
}
_LEGACY_STRUCT = {
    "en planta baixa": "pb", "de planta baixa": "pb", "en planta baja": "pb", "de planta baja": "pb",
    "sense nivell de soterrani": "sense_soterrani", "sin nivel de sótano": "sense_soterrani",
    "amb nivell de soterrani": "soterrani", "de soterrani": "soterrani", "con nivel de sótano": "soterrani",
}


def _floors_shape(num_floors: str | None, has_basement: Any) -> tuple[bool, bool, bool]:
    """(soterrani, només planta baixa, porxo) a partir de la notació de plantes («Pb+1Pp», «PB (planta baixa)+porxada»…)."""
    nf = (num_floors or "").strip()
    basement = bool(_to_bool(has_basement)) or bool(re.search(r"\bP[Ss]\b|soterr|s[oó]tano|semis[oòó]t", nf, re.IGNORECASE))
    has_pb = bool(re.search(r"\bP[Bb]\b|planta baixa|planta baja", nf, re.IGNORECASE))
    has_pp = bool(re.search(r"\bP[Pp]\b|\d\s*P[Pp]|\+\s*\d|pis superior|planta pis|\bPB\s*\+\s*[1-9]", nf, re.IGNORECASE)) \
        and not re.search(r"sense pis superior|sin piso superior", nf, re.IGNORECASE)
    ground_only = has_pb and not has_pp
    porxo = bool(re.search(r"porx", nf, re.IGNORECASE))
    return basement, ground_only, porxo


def building_structure_clause(num_floors: str | None, has_basement: Any = None, lang: str = "ca",
                              current: str | None = None) -> NarrativeChoice:
    """Clàusula sencera després de «…construcció d'una estructura ». `current` (valor del wizard) mana si no és un dels
    valors curts antics («en planta baixa», «sense nivell de soterrani», «amb nivell de soterrani»), que es mapegen."""
    table = _STRUCT_ES if lang == "es" else _STRUCT_CA
    basement, ground_only, porxo = _floors_shape(num_floors, has_basement)
    porxo_txt = (" y porche" if lang == "es" else " i porxo") if porxo else ""
    cur = (current or "").strip()
    if cur and cur.lower().rstrip(".") not in _LEGACY_STRUCT:
        # text de l'Eva (o clàusula ja sencera): tal qual, la resta com a candidats
        chosen = None
    else:
        chosen = _LEGACY_STRUCT.get(cur.lower().rstrip(".")) if cur else None
    if chosen is None and cur and cur.lower().rstrip(".") not in _LEGACY_STRUCT:
        value, why = cur, "valor del wizard"
    else:
        key = chosen or ("soterrani" if basement else ("pb" if ground_only else "sense_soterrani"))
        value = table[key].format(porxo=porxo_txt)
        why = {"pb": "només planta baixa (Rubí, Bell-lloc)", "sense_soterrani": "amb pis i sense soterrani (Castellar, Linyola, Alcoletge)",
               "soterrani": "amb soterrani (sense exemple signat en català)"}[key]
        if chosen:
            why = f"valor curt del wizard «{cur}» → clàusula sencera"
    cands = [Candidate(value, why)]
    for k in ("pb", "sense_soterrani", "soterrani"):
        v = table[k].format(porxo=porxo_txt)
        if v != value:
            cands.append(Candidate(v, {"pb": "variant (a) dels signats", "sense_soterrani": "variant (b) dels signats",
                                       "soterrani": "amb soterrani"}[k]))
    notes = ["soterrani: cap exemple signat en català (Anciles ES és text lliure)"] if basement else []
    if not (num_floors or "").strip() and not cur:
        notes.append("plantes desconegudes: defecte «sense nivell de soterrani»")
    return NarrativeChoice(value, why, cands, notes)


def most_unfavourable_level(levels: list[dict[str, Any]] | None) -> int:
    """Número (1-based) del nivell amb φ més baix (i c més baixa); 1 si no hi ha dades."""
    if not levels:
        return 1
    best, best_key = 1, None
    for i, lv in enumerate(levels, 1):
        phi = lv.get("phi") if isinstance(lv, dict) else getattr(lv, "phi", None)
        c = lv.get("cohesion") if isinstance(lv, dict) else getattr(lv, "cohesion", None)
        try:
            key = (float(phi) if phi is not None else 99.0, float(c) if c is not None else 99.0)
        except (TypeError, ValueError):
            continue
        if best_key is None or key < best_key:
            best, best_key = i, key
    return best


def empentes_paragraph(level_number: int = 1, lang: str = "ca") -> str:
    if lang == "es":
        return (f"Para el dimensionado de los muros del sótano y para el cálculo del empuje de tierras habrá que tener en cuenta "
                f"los parámetros geomecánicos de los materiales del {ordinal(level_number, 'es', word=True)} nivel que se "
                "considera el más desfavorable.\nHabrá que tener en cuenta que en el trasdós del muro se tendrá que instalar un "
                "correcto drenaje para evitar que se acumule el agua y se produzca una sobrecarga en su trasdós.")
    return (f"Pel dimensionament dels murs que es projectin i pel càlcul de les empentes de terres caldrà tenir en compte els "
            f"paràmetres geomecànics dels materials del {ordinal(level_number)} nivell que es considera el més desfavorable.\n"
            "Cal tenir en compte que en el trasdós del mur, caldrà instal·lar un correcte drenatge per a evitar que s'acumuli "
            "aigua i es produeixi una sobrecàrrega en el seu trasdós.")


# --- Peça 3 (2026-09-07): estat del solar, assaigs de laboratori, peu de les vistes generals ---------------------

#: Vocabulari tancat de l'ESTAT DEL SOLAR (bloc 2 de «2.1.2. Descripció del solar»; `docs/ANALISI-NARRATIVA-2026-09-06.md`
#: §3.2). La frase d'entrada (accés), «En solars propers…» i «Destacar que no es poden veure aflorar…» ja són text fix de
#: la plantilla: aquí NOMÉS l'estat. Fets que tenim: construcció pròpia (Cadastre DNPRC de la parcel·la del projecte) i
#: pendent (ICGC MDT). Vegetació, tanques, desnivell exacte i plataforma de treball són judici de la visita (candidats).
_SITE_DESC_CA = {
    "buit_pla": "El solar es localitza sense construccions ni pavimentacions, anivellat a la rasant del carrer.",
    "buit_pendent": "El solar es localitza sense construccions ni pavimentacions. Topogràficament, el solar presenta pendent.",
    "buit": "El solar es localitza sense construccions ni pavimentacions.",   # pendent desconeguda (sense UTM): cap afirmació
    "construit": "El solar està actualment ocupat per una zona explanada i {edifici}.",
}
_SITE_DESC_VARIANTS_CA = {
    "buit_pla": [
        ("El solar es localitza sense construccions ni pavimentacions, anivellat a la rasant del carrer, i amb vegetació de "
         "petita alçada.", "variant amb vegetació (Bell-lloc)"),
        ("La parcel·la es localitza explanada, sense pavimentar, i amb vegetació puntual de petita alçada.",
         "variant «explanada» (Linyola)"),
    ],
    "buit_pendent": [
        ("El solar es localitza sense construccions ni pavimentacions. Topogràficament, fa una lleugera baixada, tot i que "
         "la zona de treball es mostra totalment plana.", "variant «lleugera baixada» (Rubí)"),
        ("El solar es localitza sense construccions ni pavimentacions, s'ha realitzat un desbroç de la zona de treball i "
         "s'ha adequat un accés a la zona de treball. Topogràficament, el solar presenta pendent, amb una plataforma de "
         "treball, la única on es pot emplaçar la màquina.", "variant «plataforma de treball» (Castellar)"),
    ],
    "construit": [],
}
_SITE_DESC_ES = {
    "buit_pla": "La parcela se localiza sin construcciones ni pavimentaciones, nivelada a la rasante de la calle.",
    "buit_pendent": "La parcela se localiza sin construcciones ni pavimentaciones. Topográficamente, la parcela presenta pendiente.",
    "buit": "La parcela se localiza sin construcciones ni pavimentaciones.",
    "construit": "La parcela está actualmente ocupada por una zona explanada y {edifici}.",
}
_SITE_DESC_VARIANTS_ES = {
    "buit_pla": [
        ("El interior de la parcela se localiza bastante explanada, sin pavimentaciones, y con vegetación de pequeña "
         "envergadura.", "variant «explanada» (Anciles)"),
    ],
    "buit_pendent": [],
    "construit": [],
}


_PLANTES_CA = {2: "dues", 3: "tres", 4: "quatre", 5: "cinc", 6: "sis"}


def _building_phrase(own_building: dict[str, Any] | None, lang: str) -> str:
    n = int((own_building or {}).get("num_floors_above") or 0)
    if lang == "es":
        return "un edificio de planta baja" if n <= 1 else f"un edificio de {n} plantas"
    if n <= 1:
        return "un edifici en planta baixa"
    return f"un edifici de {_PLANTES_CA.get(n, str(n))} plantes"


def site_description_sentence(slope_percent: Any = None, own_building: dict[str, Any] | None = None, lang: str = "ca",
                              current: str | None = None) -> NarrativeChoice:
    """Estat del solar (paràgraf `{{ site_description }}`, només el bloc 2 de §3.2) per criteri:

    - parcel·la pròpia amb edifici al Cadastre (DNPRC: `has_building` i plantes sobre rasant) → «El solar està actualment
      ocupat per una zona explanada i un edifici en planta baixa.» (Alcoletge);
    - pendent ICGC > `SLOPE_THRESHOLD_PCT` → «…sense construccions ni pavimentacions. Topogràficament, el solar presenta
      pendent.» (Castellar, Rubí);
    - si no → «…sense construccions ni pavimentacions, anivellat a la rasant del carrer.» (Bell-lloc, Linyola).
    `current` (text de l'Eva al wizard, ≥ 4 paraules) mana i el criteri queda com a candidat. `own_building` None =
    Cadastre no consultat: es suposa sense construccions i s'anota."""
    table = _SITE_DESC_ES if lang == "es" else _SITE_DESC_CA
    variants = _SITE_DESC_VARIANTS_ES if lang == "es" else _SITE_DESC_VARIANTS_CA
    try:
        slope = float(slope_percent) if slope_percent not in (None, "") else None
    except (TypeError, ValueError):
        slope = None
    built = bool((own_building or {}).get("has_building")) and int((own_building or {}).get("num_floors_above") or 0) >= 1
    if built:
        key, why = "construit", "parcel·la pròpia amb edifici al Cadastre (Alcoletge)"
    elif slope is None:
        key, why = "buit", "sense edifici al Cadastre; pendent desconeguda (sense UTM): cap afirmació topogràfica"
    elif slope > SLOPE_THRESHOLD_PCT:
        key, why = "buit_pendent", f"sense edifici al Cadastre i pendent {slope:.0f} % > {SLOPE_THRESHOLD_PCT:.0f} % (Castellar, Rubí)"
    else:
        key, why = "buit_pla", f"sense edifici al Cadastre i pendent {slope:.0f} % (Bell-lloc, Linyola)"
    default = table[key].format(edifici=_building_phrase(own_building, lang))
    cands = [Candidate(default, why)]
    cands += [Candidate(v, src) for v, src in variants.get(key, [])]
    for k in ("buit_pla", "buit_pendent", "construit"):
        if k != key:
            cands.append(Candidate(table[k].format(edifici=_building_phrase(own_building, lang)), f"cap «{k.replace('_', ' ')}»"))
    notes: list[str] = []
    if own_building is None:
        notes.append("construcció pròpia sense font (Cadastre DNPRC no consultat): es suposa sense construccions")
    notes.append("vegetació, tanques, desnivell respecte el carrer i plataforma de treball: judici de la visita")
    cur = (current or "").strip()
    if len(cur.split()) >= 4:
        return NarrativeChoice(cur, "text del wizard (Eva)", [Candidate(cur, "wizard")] + cands, notes)
    return NarrativeChoice(default, why, cands, notes)


# Assaigs de laboratori (cel·la «Assaigs realitzats» de la taula del laboratori, `{{ lab_tests_text }}`). Font: el bloc
# «ASSAIGS REALITZATS:» de l'informe GTL (una línia per assaig amb la norma UNE). Fórmules de l'Eva (signats CA):
#   sulfats sol   «1 assaig de contingut en sulfats UNE 83963 : 2008»            (Castellar, Bell-lloc)
#   en llista     «Anàlisi granulomètrica d'un sòl per tamissat UNE 103101/95»   (Rubí)
#                 «Assaig de Límits d'Atterberg UNE 103103/94 – 104/93»           (Linyola; Rubí «Determinació de Límits
#                 d'Atterberg d'un sòl UNE 103103/94-104/93», Alcoletge «Assaig de plasticitat de Límits d'Atterberg…»)
#                 «Assaig d'expansivitat Lambe UNE 103600/96»                     (Linyola escriu «UNE 103500/94»: errata,
#                 la norma del Lambe és la UNE 103600:1996 que cita el GTL; no es reprodueix)
#                 «Assaig de contingut en sulfats UNE 83963 : 2008»               (Rubí, Linyola)
# Ordre canònic (3/3 llistes signades): granulometria, Atterberg, Lambe, sulfats, la resta. ES: la línia literal del GTL
# («Determinación del contenido en ión sulfato en suelos UNE 83963 / 08», Vilanova i Anciles).
_GTL_KINDS = (
    ("granulometria", re.compile(r"(?i)granulom")),
    ("atterberg", re.compile(r"(?i)atterberg|l[ií]mit\s+l[ií]quid|l[ií]mit\s+pl[aà]stic|plasticit")),
    ("lambe", re.compile(r"(?i)lambe|expansiv")),
    ("sulfats", re.compile(r"(?i)sulfat")),
    ("humitat", re.compile(r"(?i)humitat|humedad")),
)
_UNE_RE = re.compile(r"UNE(?:-EN)?\s*\d{4,6}(?:\s*[:/]\s*\d{2,4})?")
_KIND_ORDER = ("granulometria", "atterberg", "lambe", "sulfats", "humitat", "altres")


def parse_gtl_tests(block: str | None) -> list[dict[str, str]]:
    """Línies del bloc «ASSAIGS REALITZATS:» del GTL → [{'kind', 'une', 'literal'}], una entrada per assaig (els dos
    límits d'Atterberg s'ajunten en una). Text sobreposat del peu («PROSPECCIÓ», «TPS,») fora."""
    out: list[dict[str, str]] = []
    for raw in re.split(r"[\n\r]+", block or ""):
        line = re.sub(r"\s+", " ", raw).strip()
        line = re.sub(r"\b(PROSPECCI[ÓO]|TPS,?|DEL SUBS[ÒO]L,?|SL)\b", "", line).strip(" ,")
        if not line:
            continue
        une = _UNE_RE.search(line)
        kind = next((k for k, rx in _GTL_KINDS if rx.search(line)), None)
        if kind is None and une is None:
            continue
        kind = kind or "altres"
        une_txt = re.sub(r"\s+", " ", une.group(0)).strip() if une else ""
        literal = re.sub(r"\s*UNE.*$", "", line).strip()
        prev = next((e for e in out if e["kind"] == kind and kind == "atterberg"), None)
        if prev is not None:
            if une_txt and une_txt not in prev["une"]:
                prev["une"] = f"{prev['une']} – {une_txt}" if prev["une"] else une_txt
            prev["literal"] += "\n" + literal + (f" {une_txt}" if une_txt else "")
            continue
        out.append({"kind": kind, "une": une_txt, "literal": literal + (f" {une_txt}" if une_txt else "")})
    out.sort(key=lambda e: _KIND_ORDER.index(e["kind"]) if e["kind"] in _KIND_ORDER else len(_KIND_ORDER))
    return out


def _une_short(une: str) -> str:
    """«UNE 103101 / 95» → «103101/95»; «UNE 103103 / 94 – UNE 103104 / 93» → «103103/94 – 104/93»."""
    parts = [re.sub(r"\s", "", p.replace("UNE", "")) for p in re.split(r"\s*–\s*", une) if p.strip()]
    if not parts:
        return ""
    if len(parts) == 2 and parts[0][:3] == parts[1][:3]:
        return f"{parts[0]} – {parts[1][3:]}"
    return " – ".join(parts)


def lab_tests_lines(block: str | None, lang: str = "ca") -> NarrativeChoice:
    """Cel·la «Assaigs realitzats» per criteri a partir del bloc del GTL. Sense bloc → buit (cap assaig inventat)."""
    tests = parse_gtl_tests(block)
    if not tests:
        return NarrativeChoice("", "sense bloc «ASSAIGS REALITZATS» del GTL", [], ["laboratori: cap llista d'assaigs llegida"])
    literal = "\n".join(t["literal"] for t in tests)
    if lang == "es":
        _ES = {
            "granulometria": "Análisis granulométrico de un suelo por tamizado UNE 103101 / 95",
            "atterberg": "Determinación de los límites de Atterberg UNE 103103 / 94 – 104 / 93",
            "lambe": "Ensayo de expansividad Lambe UNE 103600 / 96",
            "sulfats": "Determinación del contenido en ión sulfato en suelos UNE 83963 / 08",
        }
        gtl_is_es = any(re.search(r"(?i)determinaci[óo]n|ensayo|suelos", t["literal"]) for t in tests)
        value = literal if gtl_is_es else "\n".join(_ES.get(t["kind"], t["literal"]) for t in tests)
        cands = [Candidate(value, "línia literal del GTL (Vilanova, Anciles)" if gtl_is_es else "GTL en català traduït")]
        if value != literal:
            cands.append(Candidate(literal, "línies literals del GTL"))
        return NarrativeChoice(value, cands[0].source, cands)
    lines: list[str] = []
    rubi: list[str] = []
    only_sulfats = len(tests) == 1 and tests[0]["kind"] == "sulfats"
    for t in tests:
        k, une = t["kind"], _une_short(t["une"])
        if k == "sulfats":
            line = ("1 assaig de contingut en sulfats" if only_sulfats else "Assaig de contingut en sulfats") + " UNE 83963 : 2008"
            lines.append(line); rubi.append(line)
        elif k == "granulometria":
            line = f"Anàlisi granulomètrica d'un sòl per tamissat UNE {une or '103101/95'}"
            lines.append(line); rubi.append(line)
        elif k == "atterberg":
            u = une or "103103/94 – 104/93"
            lines.append(f"Assaig de Límits d'Atterberg UNE {u}")
            rubi.append(f"Determinació de Límits d'Atterberg d'un sòl UNE {u.replace(' – ', '-')}")
        elif k == "lambe":
            line = f"Assaig d'expansivitat Lambe UNE {une or '103600/96'}"
            lines.append(line); rubi.append(line)
        elif k == "humitat":
            line = f"Determinació de la humitat d'un sòl UNE {une}".strip()
            lines.append(line); rubi.append(line)
        else:
            lines.append(t["literal"]); rubi.append(t["literal"])
    value = "\n".join(lines)
    why = "sulfats sol: «1 assaig de…» (Castellar, Bell-lloc)" if only_sulfats else "llista en ordre canònic (Rubí, Linyola)"
    cands = [Candidate(value, why)]
    if "\n".join(rubi) != value:
        cands.append(Candidate("\n".join(rubi), "variant «Determinació de Límits d'Atterberg d'un sòl» (Rubí)"))
    if literal != value:
        cands.append(Candidate(literal, "línies literals del GTL"))
    notes = ["Lambe: norma del GTL (UNE 103600/96); Linyola signat «UNE 103500/94» és errata"] if any(t["kind"] == "lambe" for t in tests) else []
    return NarrativeChoice(value, why, cands, notes)


def photo_site_caption(num_site_photos: int, lang: str = "ca") -> str:
    """Peu sencer del bloc «vistes generals» (paràgraf `{{ photo_site_text }}`, condicional). 0 → '' (el bloc desapareix:
    Castellar, Linyola, Alcoletge, Anciles; la Fotografia 1 és la màquina). Bell-lloc: «Fotografia 1 i Fotografia 2. Vistes
    generals de la zona d'estudi.»; Rubí: «Fotografia 1. Vista general de la zona d'estudi (Google Earth, Agost 2024).»"""
    try:
        n = int(num_site_photos or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return ""
    if lang == "es":
        return ("Fotografía 1 y Fotografía 2. Vistas generales de la zona de estudio." if n >= 2
                else "Fotografía 1. Vista general de la zona de estudio.")
    return ("Fotografia 1 i Fotografia 2. Vistes generals de la zona d'estudi." if n >= 2
            else "Fotografia 1. Vista general de la zona d'estudi.")
