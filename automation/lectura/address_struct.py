"""Objecte estructurat de l'adreça — sortida del lector, validada a Python.

Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` (decisions D1, D2, D3b i A1). El skill de
lectura és qui interpreta l'adreça —és l'únic que veu totes les grafies del mateix carrer dins
d'un projecte (comanda N20, pressupost bloc OBRA, fitxa C7, plànol, correus)— i n'emet un
concepte extra, `street_address_struct`, amb les **grafies alternatives**. Aquest mòdul el
valida i el converteix en pistes per al Cadastre.

Tres regles que no es poden relaxar:

1. **Eix via/municipi sí, eix portal no.** Les alternatives valen per al nom de via i per al
   municipi, on les variants són ortogràfiques i designen el mateix objecte del món. Els
   portals segueixen sortint de `portals_from_address` (regex determinista): 18A i 18B són dos
   edificis amb dos propietaris, i «provar alternatives» aquí ressuscitaria el bug 18B→18A.
   Els portals de l'objecte només serveixen per **contrastar** i deixar-ne nota.
2. **Res del model no arriba a un valor sense passar per una llista real.** Una alternativa és
   només un intent de consulta més; qui decideix segueix sent `resolve_via` (conjunt tancat) i
   `municipis.lookup` (padró).
3. **Un objecte invàlid no fa mal.** `claude -p` no té sortida estructurada (per això A1 diu
   esquema + exemples al prompt i validació aquí). Si l'objecte no passa la validació,
   s'ignora i tot funciona com abans amb el text lliure: es perd la millora, mai s'guanya un
   error. Per això NO hi ha bucle de re-pregunta: la degradació ja és segura.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: Nom del concepte extra que emet el skill. Cau a `extra_concepts` de `_decisions.json`
#: perque no es una de les `ALLOWED_FIELD_KEYS`: no contamina les variables de l'informe.
STRUCT_CONCEPT = "street_address_struct"

#: Prou per a les variants reals (ca/es, dígits/lletres, accents, abreviatures); un model que
#: en dispari 40 esta al·lucinant, no ajudant.
MAX_ALTERNATIVES = 8
#: Mateix sostre que `cadastre_reader._MAX_PORTALS`.
MAX_PORTALS = 6
MAX_LEN = 120

_PORTAL_RE = re.compile(r"^\d{1,4}\s*[A-Za-z]?$")
_HAS_LETTER_RE = re.compile(r"[^\W\d_]")

#: Pis/porta escrits com a ordinal ENGANXAT al numero ("3r", "2n", "4t", "5è", "1er", "3º"):
#: mai son portals. Definit AQUI i importat per `cadastre_reader.portals_from_address`: es
#: vocabulari d'adreces i n'hi ha d'haver una sola definicio (el projecte ja va pagar car tenir
#: dues llistes ad-hoc divergents per als components, vegeu `normalize.COMPONENT_VALUE_KEY`).
#: La `a` de "2a" NO hi es a posta —"18A" es un portal de debo— i la `e` tampoc ("12E"): val
#: mes deixar passar un pis que no pas menjar-se un portal.
FLOOR_ORDINAL_RE = re.compile(r"\d+\s*[ºª]|\b\d+(?:er|[rnt]|è)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AddressStruct:
    """Adreça interpretada pel lector. `nom_via`/`municipi` son la lectura principal; les
    llistes d'alternatives son grafies del MATEIX lloc, mai llocs diferents."""

    nom_via: str
    municipi: str
    tipus_via: str = ""
    nom_via_alternatives: tuple[str, ...] = ()
    portals: tuple[str, ...] = ()
    municipi_alternatives: tuple[str, ...] = ()
    fonts: tuple[str, ...] = field(default=())

    def via_hints(self) -> list[str]:
        """Nom principal primer, després les alternatives, sense repeticions."""
        return _dedup([self.nom_via, *self.nom_via_alternatives])

    def municipi_hints(self) -> list[str]:
        return _dedup([self.municipi, *self.municipi_alternatives])


def _dedup(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = " ".join(str(v).split()).casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(" ".join(str(v).split()))
    return out


def _clean_name(value: Any) -> str | None:
    """Un nom utilitzable: text, amb almenys una lletra, no massa llarg."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > MAX_LEN or not _HAS_LETTER_RE.search(text):
        return None
    return text


def _clean_names(raw: Any, problems: list[str], where: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        problems.append(f"{where}: s'esperava una llista, ha arribat {type(raw).__name__}")
        return ()
    out: list[str] = []
    for item in raw:
        name = _clean_name(item)
        if name is None:
            problems.append(f"{where}: alternativa descartada ({item!r})")
            continue
        out.append(name)
    out = _dedup(out)
    if len(out) > MAX_ALTERNATIVES:
        problems.append(f"{where}: {len(out)} alternatives, se'n conserven {MAX_ALTERNATIVES}")
        out = out[:MAX_ALTERNATIVES]
    return tuple(out)


def _clean_portals(raw: Any, problems: list[str]) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        problems.append(f"portals: s'esperava una llista, ha arribat {type(raw).__name__}")
        return ()
    out: list[str] = []
    for item in raw:
        text = str(item).strip() if isinstance(item, (str, int)) and not isinstance(item, bool) else ""
        if not _PORTAL_RE.match(text) or FLOOR_ORDINAL_RE.search(text):
            problems.append(f"portals: descartat {item!r} (no té forma de portal)")
            continue
        out.append(re.sub(r"\s+", "", text).upper())
    out = list(dict.fromkeys(out))
    if len(out) > MAX_PORTALS:
        problems.append(f"portals: {len(out)}, se'n conserven {MAX_PORTALS}")
        out = out[:MAX_PORTALS]
    return tuple(out)


def parse(raw: Any) -> tuple[AddressStruct | None, list[str]]:
    """Valida un `street_address_struct`. Retorna `(objecte | None, problemes)`.

    `None` vol dir «no utilitzable»: el cridador ha de continuar amb el text lliure de sempre.
    Els problemes són per a `notes_estructurals` i telemetria, no per a l'Eva.
    """
    problems: list[str] = []
    if not isinstance(raw, dict):
        return None, [f"street_address_struct: s'esperava un objecte, ha arribat {type(raw).__name__}"]

    nom_via = _clean_name(raw.get("nom_via"))
    municipi = _clean_name(raw.get("municipi"))
    if nom_via is None:
        problems.append("street_address_struct: `nom_via` absent o inservible")
    if municipi is None:
        problems.append("street_address_struct: `municipi` absent o inservible")
    if nom_via is None or municipi is None:
        return None, problems

    unknown = sorted(set(raw) - {
        "nom_via", "municipi", "tipus_via", "nom_via_alternatives", "portals", "municipi_alternatives",
    })
    if unknown:
        problems.append(f"street_address_struct: claus ignorades {unknown}")

    struct = AddressStruct(
        nom_via=nom_via,
        municipi=municipi,
        tipus_via=_clean_name(raw.get("tipus_via")) or "",
        nom_via_alternatives=tuple(a for a in _clean_names(raw.get("nom_via_alternatives"), problems, "nom_via_alternatives") if a.casefold() != nom_via.casefold()),
        portals=_clean_portals(raw.get("portals"), problems),
        municipi_alternatives=tuple(a for a in _clean_names(raw.get("municipi_alternatives"), problems, "municipi_alternatives") if a.casefold() != municipi.casefold()),
    )
    return struct, problems


def from_extra_concepts(extra_concepts: Any) -> tuple[AddressStruct | None, list[str]]:
    """Tria i FUSIONA els `street_address_struct` que hagin emès els documents del projecte.

    Cada document pot portar la seva grafia (la comanda escriu «C/ARBRELLS», el pressupost
    «Carrer Arbrells, 18A-18B-20»): la lectura principal és la del primer objecte vàlid i les
    dels altres passen a ser alternatives. Justament la variabilitat DINS d'un mateix projecte
    que descriu la proposta del Josep és, aquí, el material útil.
    """
    problems: list[str] = []
    if not isinstance(extra_concepts, dict):
        return None, problems
    candidates = extra_concepts.get(STRUCT_CONCEPT)
    if not isinstance(candidates, list):
        return None, problems

    structs: list[AddressStruct] = []
    fonts: list[str] = []
    for cand in candidates:
        raw = cand.get("value") if isinstance(cand, dict) else cand
        struct, probs = parse(raw)
        problems.extend(probs)
        if struct is not None:
            structs.append(struct)
            font = (cand.get("font") or cand.get("doc") or "") if isinstance(cand, dict) else ""
            if font:
                fonts.append(str(font))
    if not structs:
        return None, problems

    first = structs[0]
    via_alts = _dedup([a for s in structs for a in ([s.nom_via, *s.nom_via_alternatives])])
    muni_alts = _dedup([a for s in structs for a in ([s.municipi, *s.municipi_alternatives])])
    return (
        AddressStruct(
            nom_via=first.nom_via,
            municipi=first.municipi,
            tipus_via=first.tipus_via,
            nom_via_alternatives=tuple(a for a in via_alts if a.casefold() != first.nom_via.casefold())[:MAX_ALTERNATIVES],
            portals=first.portals,
            municipi_alternatives=tuple(a for a in muni_alts if a.casefold() != first.municipi.casefold())[:MAX_ALTERNATIVES],
            fonts=tuple(_dedup(fonts)),
        ),
        problems,
    )
