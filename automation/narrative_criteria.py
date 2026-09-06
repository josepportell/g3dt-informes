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
