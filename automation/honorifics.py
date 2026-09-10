"""Honorífic de la persona sol·licitant, com l'escriu l'Eva (bloc 2, 2026-09-07).

Als signats, la portada («A petició de:») i la frase dels antecedents porten «SR.» / «SRA.» davant del nom quan
el client és una persona (Rubí «SRA. JOANA MARTINEZ», Linyola «SRA. SÍLVIA EROLES BALAGUERÓ», Alcoletge
«SR. ALBERT SANS BONVEHI», Anciles «SRA. ALBA MARIA BARRAU CASTÁN»: 4/4) i res quan és una empresa
(Castellar «WOOD COMFORT PROMOCIONS SLU», Bell-lloc «RAMON MITJANA S.L», Vilanova «GRUPO CUENCA GUERRERO, S.L»:
3/3). A la frase, l'article: «en nom de la SRA. …» (Linyola), «el sol·licitant, el SR. …» (Bell-lloc, Alcoletge),
«la sol·licitant, la SRA. …» (Rubí).

Tot determinista: empresa per forma jurídica o vocabulari; gènere pel NOM DE PILA (llista de noms catalans i
castellans + terminació «-a» quan el nom no hi és). Si no es pot decidir (nom desconegut que no acaba en «-a»,
dues persones «X i Y»), **cap honorífic**: val més el nom sol que un tractament equivocat en un informe signat.
"""

from __future__ import annotations

import re
import unicodedata

_LEGAL_FORMS = {"SL", "SLU", "SLP", "SLL", "SA", "SAU", "SAL", "SCP", "SCCL", "SCOOP", "COOP", "CB", "AIE", "UTE",
                "LTD", "GMBH", "INC", "LLC", "BV", "SARL", "SRL", "SPA"}
_COMPANY_WORDS = {
    "promocions", "promociones", "construccions", "construcciones", "grupo", "grup", "arquitectura", "arquitectes",
    "arquitectos", "enginyeria", "ingenieria", "associats", "asociados", "ajuntament", "ayuntamiento", "comunitat",
    "comunidad", "fundacio", "fundacion", "cooperativa", "industries", "industrias", "serveis", "servicios",
    "immobiliaria", "inmobiliaria", "gestio", "gestion", "consulting", "solutions", "obres", "obras", "projectes",
    "proyectos", "estudi", "estudio", "taller", "societat", "sociedad", "empresa", "hotel", "restaurant", "bar",
    "escola", "escuela", "institut", "instituto", "universitat", "universidad", "diputacio", "diputacion",
    "generalitat", "consell", "consejo", "parroquia", "bisbat", "obispado", "germans", "hermanos", "fills", "hijos",
    "sl", "slu", "slp", "sa", "sau", "scp", "sccl",
}
_TITLES_RE = re.compile(r"^\s*(?:sr\.?|sra\.?|srs\.?|sres\.?|d\.|dn\.|dña\.|dna\.|don|doña|donya|en|na)\s+", re.I)

_FEMALE = {
    "alba", "anna", "ana", "aina", "aitana", "berta", "bruna", "carla", "clara", "cristina", "elena", "emma", "eva",
    "gemma", "georgina", "irene", "joana", "judit", "judith", "julia", "laia", "laura", "lidia", "lucia", "maria",
    "marina", "marta", "mariona", "mireia", "monica", "montse", "montserrat", "natalia", "neus", "noa", "nuria",
    "ona", "paula", "rosa", "sandra", "sara", "silvia", "sonia", "teresa", "vanessa", "vanesa", "xenia", "carme",
    "carmen", "merce", "mercedes", "dolors", "dolores", "pilar", "isabel", "roser", "meritxell", "raquel", "ester",
    "esther", "miriam", "noemi", "elisabet", "elisabeth", "beatriu", "beatriz", "angels", "angeles", "assumpta",
    "assumpcio", "immaculada", "inmaculada", "inma", "conxita", "concepcio", "concepcion", "encarna", "encarnacio",
    "remei", "trini", "trinitat", "trinidad", "lourdes", "mar", "marisol", "maribel", "rocio", "yolanda", "susana",
    "patricia", "andrea", "ariadna", "blanca", "claudia", "daniela", "elisa", "elvira", "estel", "estela", "eulalia",
    "fatima", "gloria", "helena", "ingrid", "iris", "ivet", "jana", "lorena", "magda", "maite", "marga", "margarita",
    "nerea", "olga", "rut", "ruth", "sofia", "tania", "veronica", "victoria", "virginia", "vinyet", "lola", "lluisa",
    "luisa", "josefa", "josefina", "antonia", "francesca", "francisca", "rosario", "aurea", "aurora", "amparo",
    "consuelo", "nieves", "paz", "reyes", "africa", "alicia", "amanda", "ainhoa", "leire", "nahia", "naiara", "salut",
    "consol", "nuri", "mercè", "montsе", "emilia", "julieta", "valeria", "carlota", "abril", "martina", "ariadna",
    "gisela", "anais", "nina", "aroa", "jessica", "vanessa", "belen", "begoña", "begonya", "arantxa", "itziar",
    "idoia", "miren", "edurne", "oihana", "nekane", "amaia", "ane", "irati", "june", "uxue", "carol", "carolina",
    "adriana", "alejandra", "alexandra", "angela", "antonia", "asuncion", "camila", "catalina", "cecilia", "celia",
    "dolores", "eloisa", "estefania", "eugenia", "fernanda", "florencia", "gabriela", "guadalupe", "ines", "ivana",
    "jimena", "josefina", "leticia", "lidia", "liliana", "lorena", "magdalena", "manuela", "marcela", "mariana",
    "matilde", "mercedes", "milagros", "miriam", "natividad", "noelia", "paloma", "pepa", "purificacion", "ramona",
    "rebeca", "regina", "renata", "rosalia", "sabina", "sagrario", "salome", "silvana", "soledad", "tamara",
    "valentina", "ximena", "zoe", "zaira", "ivonne", "yvonne", "isabella", "elsa", "greta", "nora", "vera", "alma",
}
_MALE = {
    "pere", "jaume", "vicenc", "jordi", "sergi", "toni", "xavi", "didac", "marc", "enric", "guillem", "lluis", "andreu",
    "bartomeu", "mateu", "josep", "oriol", "arnau", "pau", "pol", "roc", "genis", "aleix", "ferran", "ramon", "joan",
    "albert", "david", "manel", "miquel", "rafel", "salvador", "xavier", "eloi", "roger", "ignasi", "jesus", "jaime",
    "jose", "juan", "manuel", "miguel", "rafael", "angel", "antoni", "antonio", "francesc", "francisco", "carles",
    "carlos", "jorge", "luis", "pedro", "pablo", "alejandro", "andres", "javier", "sergio", "daniel", "adria",
    "adrian", "ivan", "ruben", "oscar", "alberto", "ricard", "ricardo", "victor", "eduard", "eduardo", "enrique",
    "gerard", "marti", "nil", "biel", "joel", "ot", "quim", "joaquim", "joaquin", "tomas", "lluc", "lucas", "mario",
    "alex", "iker", "unai", "asier", "kevin", "cristian", "christian", "jonathan", "isaac", "nicolau", "nicolas",
    "agusti", "agustin", "bernat", "benet", "damia", "sebastia", "julia", "julio", "emili", "emilio", "cesc", "feliu",
    "felix", "gabriel", "gil", "hug", "hugo", "ismael", "jan", "jofre", "llorenc", "lorenzo", "magi", "narcis",
    "ovidi", "ponc", "ramir", "robert", "roberto", "simo", "simon", "valenti", "vicent", "vicente", "xevi", "borja",
    "josema", "jonas", "elias", "matias", "tobias", "nicola", "sasha", "noah", "luca", "andrea",  # andrea: vegeu nota
    "abel", "adam", "aitor", "alfons", "alfonso", "alfred", "alfredo", "amadeu", "anselm", "arturo", "artur",
    "august", "aurelio", "baltasar", "basilio", "benjamin", "bernardo", "bruno", "camilo", "cesar", "cristobal",
    "damian", "diego", "domingo", "eloy", "elvis", "emilio", "ernest", "ernesto", "esteban", "esteve", "eugeni",
    "eugenio", "eusebio", "evaristo", "fabian", "fabio", "federico", "felipe", "fermin", "fernando", "florencio",
    "fortunato", "gaspar", "gonzalo", "gregorio", "guillermo", "gustavo", "hector", "heribert", "hilario", "ignacio",
    "inaki", "isidre", "isidro", "jacint", "jacinto", "jeroni", "jeronimo", "joaquin", "jon", "jordi", "josu", "leandro",
    "leo", "leon", "leonardo", "lluis", "lorenzo", "lucio", "marcel", "marcelo", "marcos", "mariano", "marino",
    "martin", "mateo", "matias", "mauricio", "maximo", "melcior", "mikel", "modest", "moises", "nacho", "nestor",
    "octavi", "octavio", "orlando", "pascual", "patxi", "pelayo", "pep", "pere", "rafa", "raimon", "ramiro", "raul",
    "remigio", "ricard", "rodrigo", "rogelio", "roman", "rosendo", "rufino", "salva", "samuel", "santi", "santiago",
    "saul", "sebastian", "sergi", "silvestre", "teodor", "teodoro", "tomeu", "ulises", "urbano", "valentin",
    "valeri", "vidal", "wenceslao", "xesc", "zacarias", "adolf", "adolfo", "pasqual", "jesus", "manolo",
}
# Nota «andrea»: en català i castellà és nom de dona (femení) però en italià d'home; la terminació «-a» mana al
# fallback. Es treu del conjunt masculí per no contradir l'ús del país.
_MALE.discard("andrea")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()


def is_company(name: str) -> bool:
    """Forma jurídica («S.L.», «SLU», «S.A.»), vocabulari d'empresa/organisme, xifres, «&» o «i/y» entre dos noms."""
    raw = (name or "").strip()
    if not raw:
        return False
    if "&" in raw or re.search(r"\d", raw):
        return True
    if re.search(r"\s(?:i|y|e)\s", raw, re.I):        # «SÍLVIA EROLES i JAUME NADAL»: dues persones → sense tractament
        return True
    tokens = [re.sub(r"[.,;:()]", "", t) for t in _norm(raw).split()]
    for t in tokens:
        if t.upper() in _LEGAL_FORMS or t in _COMPANY_WORDS:
            return True
    return False


def first_name_gender(name: str) -> str:
    """'f' / 'm' pel nom de pila (primer token després d'un tractament previ), '' si no es pot decidir."""
    raw = _TITLES_RE.sub("", (name or "").strip())
    if not raw:
        return ""
    first = re.sub(r"[^\w-]", "", _norm(raw).split()[0]).replace("-", "")
    if not first:
        return ""
    if first in _FEMALE:
        return "f"
    if first in _MALE:
        return "m"
    if first.endswith("a") and len(first) > 2:
        return "f"
    return ""


def honorific(name: str, lang: str = "ca") -> str:
    """«SR.» / «SRA.» per a una persona; «» per a una empresa o quan no es pot decidir. Igual en ca i es."""
    if is_company(name):
        return ""
    g = first_name_gender(name)
    return {"f": "SRA.", "m": "SR."}.get(g, "")


def with_honorific(name: str, lang: str = "ca") -> str:
    """Portada («A petició de:»): «SRA. SÍLVIA EROLES BALAGUERÓ», «WOOD COMFORT PROMOCIONS S.L.U.». Idempotent."""
    raw = (name or "").strip()
    if not raw:
        return ""
    if _TITLES_RE.match(raw):
        return raw
    h = honorific(raw, lang)
    return f"{h} {raw}" if h else raw


def de_party(name: str, lang: str = "ca") -> str:
    """«en nom {{ client_de }}»: «de la SRA. X» / «del SR. X» / «de RAMON MITJANA S.L.» / ca «d'ABN …». Buit → «»."""
    full = with_honorific(name, lang)
    if not full:
        return ""
    m = re.match(r"^(SRA?)\.\s+", full, re.I)
    if m:
        return ("de la " if m.group(1).upper() == "SRA" else "del ") + full
    if lang == "ca" and full[0].upper() in "AEIOUÀÁÈÉÍÏÒÓÚÜH":
        return f"d'{full}"
    return f"de {full}"
