"""Padró de municipis de Catalunya — resolució OFFLINE (grafia INE + grafia i codis Cadastre).

Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` §4 i §9 (peça 2). Dades:
`automation/data/municipis_padro_cadastre.json` — 947 municipis, la grafia oficial de l'INE
aparellada 947/947 amb la del Cadastre i els codis `(cp, cm)` per `ine_code` (`25048` = cp 25 /
cm 48). Baixat del Cadastre el 2026-09-01 amb 4 crides (una per província).

**Determinista, cost 0, sense xarxa** — el contracte de `g3_templates.py`, que és qui més el fa
servir, prohibeix la xarxa, no les dades. Cap capa difusa: un municipi mal escrit val més
deixar-lo sense confirmar que acostar-lo al veí (ERR = 0 mana sobre la cobertura).

Dues coses que el fitxer té i que no es veuen a ull nu:

- **L'article canvia de banda.** 136 municipis són `"Ametlla del Vallès, L'"` a l'INE i
  `"L' AMETLLA DEL VALLES"` al Cadastre. La clau de comparació el treu dels dos extrems.
- **Fora de Catalunya no hi és.** `lookup` retorna `None` per a Anciles (llogaret de Benasc,
  Osca): «no consta al padró» vol dir *o* de fora de Catalunya *o* que no és un municipi, mai
  «no existeix».
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Modul-level perque els tests el puguin `monkeypatch.setattr` (mateix patro que
#: `municipal_data.DATA_FILE` i `cadastre_reader.CACHE_DIR`).
PADRO_FILE = Path(__file__).parent / "data" / "municipis_padro_cadastre.json"

#: Articles que poden anar davant o darrere del nom ("L' Ametlla", "Ametlla, L'").
_ARTICLES = ("L'", "EL", "LA", "ELS", "LES")
#: Partícules que no distingeixen dos municipis: "Vilanova Segrià" i "Vilanova de Segrià" son
#: el mateix lloc escrit amb la preposició que G3 s'empassa als títols de PLAN_COST.
_PARTICLES = frozenset({"DE", "DEL", "DELS", "D", "LA", "LES", "EL", "ELS", "I", "NA", "EN", "N"})

_PAREN_RE = re.compile(r"\([^)]*\)")
_TRAILING_ARTICLE_RE = re.compile(r",\s*(?:" + "|".join(re.escape(a) for a in _ARTICLES) + r")\s*$")
_LEADING_ARTICLE_RE = re.compile(r"^(?:L\s*'|(?:EL|LA|ELS|LES)\b)\s*")


@dataclass(frozen=True)
class Municipi:
    """Una fila del padró, més per quina capa s'hi ha arribat."""

    ine_code: str
    name_ine: str
    name_cadastre: str
    province: str
    province_cadastre: str
    cp: str
    cm: str
    match_layer: str  # "exacte" | "forma curta" | "preposicions"


_PADRO: list[dict] | None = None
_BY_KEY: dict[str, dict] | None = None
_BY_PARTICLES: dict[tuple[str, ...], list[dict]] | None = None


def _norm(text: str) -> str:
    plain = unicodedata.normalize("NFD", str(text or ""))
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", plain).upper().strip()


def _key(name: str) -> str:
    """Clau de comparació: sense accents, majúscules, sense parèntesis i sense article.

    `"Rubí (Barcelona)"`, `"RUBI"` i `"Rubí"` donen tots `"RUBI"`; `"Ametlla del Vallès, L'"`
    i `"L' AMETLLA DEL VALLES"` donen tots dos `"AMETLLA DEL VALLES"`.
    """
    text = _norm(_PAREN_RE.sub(" ", str(name or "")))
    text = _TRAILING_ARTICLE_RE.sub("", text).strip(" ,.-")
    text = _LEADING_ARTICLE_RE.sub("", text).strip(" ,.-")
    return re.sub(r"\s+", " ", text).strip()


def _particle_key(name: str) -> tuple[str, ...]:
    return tuple(t for t in _key(name).split() if t not in _PARTICLES)


def _load() -> list[dict]:
    global _PADRO
    if _PADRO is None:
        try:
            _PADRO = json.loads(PADRO_FILE.read_text(encoding="utf-8"))["municipalities"]
        except (OSError, ValueError, KeyError) as e:
            logger.warning(f"municipis: no s'ha pogut llegir el padró {PADRO_FILE}: {e}")
            _PADRO = []
    return _PADRO


def _indexes() -> tuple[dict[str, dict], dict[tuple[str, ...], list[dict]]]:
    global _BY_KEY, _BY_PARTICLES
    if _BY_KEY is None or _BY_PARTICLES is None:
        by_key: dict[str, dict] = {}
        by_particles: dict[tuple[str, ...], list[dict]] = {}
        for row in _load():
            for name in (row["name_ine"], row["name_cadastre"]):
                by_key.setdefault(_key(name), row)
            by_particles.setdefault(_particle_key(row["name_ine"]), []).append(row)
        _BY_KEY, _BY_PARTICLES = by_key, by_particles
    return _BY_KEY, _BY_PARTICLES


def reset_cache() -> None:
    """Buida els índexs (per als tests que canvien `PADRO_FILE`)."""
    global _PADRO, _BY_KEY, _BY_PARTICLES
    _PADRO = _BY_KEY = _BY_PARTICLES = None


def _hit(row: dict, layer: str) -> Municipi:
    return Municipi(
        ine_code=row["ine_code"],
        name_ine=row["name_ine"],
        name_cadastre=row["name_cadastre"],
        province=row["province"],
        province_cadastre=row["province_cadastre"],
        cp=row["cp"],
        cm=row["cm"],
        match_layer=layer,
    )


def lookup(hint: str) -> Municipi | None:
    """Municipi del padró que correspon a `hint`, o `None` si no es pot decidir.

    Tres capes, totes exigint un **sol** guanyador (empat = `None`, mai triar):

      1. **exacte**: la clau del llegit és la d'un municipi (`"CASTELLAR DEL VALLÈS"`);
      2. **forma curta**: el llegit és el començament d'un sol municipi — la forma que fa
         servir G3 (`"BELL-LLOC"` → `Bell-lloc d'Urgell`, `"CERDANYOLA"` →
         `Cerdanyola del Vallès`). `"CASTELLAR"` encaixa amb quatre → `None`;
      3. **preposicions**: mateixes paraules ignorant `de/del/la/i/…`
         (`"VILANOVA SEGRIÀ"` → `Vilanova de Segrià`).

    Sense capa difusa a posta: `"CATELLAR"` (l'errata real del nom d'un fitxer del corpus) ha
    de quedar sense confirmar, no acostar-se a `Castellar del Vallès`.
    """
    key = _key(hint)
    if not key:
        return None
    by_key, by_particles = _indexes()

    row = by_key.get(key)
    if row is not None:
        return _hit(row, "exacte")

    prefix = [r for k, r in by_key.items() if k.startswith(key + " ")]
    unique = {r["ine_code"]: r for r in prefix}
    if len(unique) == 1:
        return _hit(next(iter(unique.values())), "forma curta")
    if len(unique) > 1:
        logger.debug(f"municipis: '{hint}' és el començament de {len(unique)} municipis: sense decidir")
        return None

    rows = by_particles.get(_particle_key(hint)) or []
    if len(rows) == 1:
        return _hit(rows[0], "preposicions")
    return None
