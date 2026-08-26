"""Fase 13(a) — `AutoExtractionResult` persistit a disc (`validation/_auto_result.json`).

Per què (disseny `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §7.1):
TEMPS 1 (FileMiner + `groq_miner` + probes ConceptScout + deep-folder classify +
APIs HTTP) es torna a executar **sencer a cada arrencada del servidor**, encara
que ni un sol fitxer del projecte hagi canviat. Mesurat aquí sobre Castellar
(còpia local, caches de disc calentes): 43-64 s. Al diagnòstic 23/08, a la
màquina de l'Eva: ~141 s. Aquest mòdul el desa i el torna a llegir.

**Envoltant, mai a dins** (disseny §9): `automation/auto_extractor.py` és via B i
NO es pot editar. Els cridadors (`web/wizard_service.py`, `web/lectura_service.py`)
demanen `load()` abans de cridar `auto_extract()` i `save()` després. Aquest mòdul
no importa res de la via B a nivell de mòdul: totes les importacions són mandroses
(dins de funció) per no crear curses d'importació circular
(memòria `project_ai_pipeline_init_must_stay_empty`).

Invalidació — dues barreres independents:

1. **`inputs_md5`** — md5 del *contingut* de tots els fitxers d'entrada del
   projecte. Contingut i no `mida+mtime` perquè el delta-sync (Fase 11) copiarà
   fitxers de la xarxa al workspace i una còpia canvia l'mtime sense canviar res:
   amb `mtime` la cache no encertaria mai després d'un sync. Cost mesurat:
   0,46 s per als 56 MB de Castellar — negligible contra els 43-141 s que estalvia.

   S'exclouen NOMÉS els fitxers que el propi pipeline escriu dins de la carpeta
   (altrament la cache s'invalidaria a si mateixa). Comprovat empíricament
   (snapshot md5 de les 173 entrades abans/després d'un `auto_extract`): l'única
   cosa que canvia és `file_mapping.json`. La resta de sortides viuen sota
   `validation/`. La llista d'exclusions és curta i conservadora a propòsit:
   excloure de menys costa una re-execució; excloure de més serveix dades velles.

2. **TTL de 30 dies** — `inputs_md5` no veu els camps que vénen d'ICGC/Cadastre
   per HTTP: la parcel·la pot canviar sense que cap fitxer del projecte es mogui.
   Passats 30 dies l'entrada es descarta sencera i TEMPS 1 es torna a executar.

A més, `CACHE_VERSION` invalida-ho tot quan canvia la forma serialitzada o les
fases d'`auto_extract`.

**Només es cacheja l'execució COMPLETA** (`auto_extract(project_path)`). La crida
de diagnòstic `auto_extract(project_path, skip_phase3=True)` (`web/api.py`, botó
d'anàlisi Groq) NO passa per aquí: el seu resultat no té la Fase 3 i enverinaria
la cache.

Fallada = sempre cache freda, mai excepció cap amunt: llegir o escriure la cache
és una optimització, i cap error seu pot deixar l'Eva sense prefills.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import tempfile
import types
import typing
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

logger = logging.getLogger(__name__)

# Puja-la quan canviï la forma serialitzada o les fases d'`auto_extract`.
CACHE_VERSION = 1

# Vida màxima d'una entrada (motiu: els camps HTTP, vegeu la capçalera).
TTL_DAYS = 30

_CACHE_RELPATH = PurePosixPath("validation/_auto_result.json")

# Sortides del pipeline dins la carpeta del projecte — fora de l'`inputs_md5`.
_EXCLUDED_DIRS = {"validation"}
_EXCLUDED_ROOT_FILES = {"file_mapping.json", "user_data.json", "_user_data_prev.json"}

# Claus de `user_data.json` que `auto_extract` llegeix (Fase 3: UTM, adreça,
# superfície — `automation/auto_extractor.py` L.267-412, 1330, 1551-1584).
# Al camí del wizard `_clear_stale_user_data()` ja ha reanomenat el fitxer abans
# que arribem aquí, així que normalment no hi és; s'inclou per als cridadors que
# no el reanomenen.
_USER_DATA_INPUT_KEYS = (
    "utm_x", "utm_y", "superficie_parcela_m2", "superficie_cadastral_m2",
    "street_address", "site_address", "site_municipality", "client_address",
)

# Sortides que `auto_extract` escriu i que `_merge_prefills` torna a llegir del
# DISC (no del `AutoExtractionResult`): `file_mapping.json` a
# `wizard_service._read_file_mapping` i `concept_map.json` a `merged['_concept_map']`.
# Estan fora de l'`inputs_md5` a posta (canvien a cada execució i invalidarien la
# cache que acaben d'omplir), i per tant un esborrat seu passaria desapercebut:
# es desa quines hi havia en desar i es comprova que hi segueixen sent.
_COMPANION_OUTPUTS = ("file_mapping.json", "validation/concept_map.json")

# Sostre d'events desats per replay (§ `save`): TEMPS 1 n'emet ~80 per a un
# projecte de 56 fitxers; el sostre només evita un fitxer patològic.
_MAX_EVENTS = 2000


@dataclasses.dataclass
class CachedRun:
    """Entrada vàlida de la cache: el resultat + els events que va emetre."""
    result: Any                      # AutoExtractionResult
    events: list[tuple[str, dict]] = dataclasses.field(default_factory=list)
    saved_at: datetime | None = None
    age_days: float = 0.0


# ---------------------------------------------------------------------------
# Estat / rutes
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """`G3DT_AUTO_RESULT_CACHE=0` la desactiva; `G3DT_NO_CACHE=1` també (mateixa
    convenció que la cache en memòria de `wizard_service.get_prefills`)."""
    if os.environ.get("G3DT_NO_CACHE") == "1":
        return False
    return os.environ.get("G3DT_AUTO_RESULT_CACHE", "1").strip().lower() not in ("0", "false", "no")


def cache_path(project_path: str | Path) -> Path:
    return Path(project_path) / _CACHE_RELPATH


def invalidate(project_path: str | Path) -> None:
    """Esborra l'entrada. Idempotent, mai llança."""
    try:
        cache_path(project_path).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("auto_result cache: no s'ha pogut esborrar (%s)", exc)


# ---------------------------------------------------------------------------
# Empremta dels fitxers d'entrada
# ---------------------------------------------------------------------------

def _iter_input_files(project_path: Path):
    """Fitxers d'entrada del projecte, ordenats per path relatiu POSIX."""
    root = Path(project_path)
    found: list[tuple[str, Path]] = []
    try:
        candidates = list(root.rglob("*"))
    except OSError as exc:
        logger.warning("auto_result cache: rglob ha fallat a %s (%s)", root, exc)
        return []
    for p in candidates:
        try:
            if not p.is_file():
                continue
            rel = p.relative_to(root)
        except OSError:
            continue
        parts = rel.parts
        name = parts[-1]
        if any(part.lower() in _EXCLUDED_DIRS for part in parts[:-1]):
            continue
        if name.startswith("~$"):
            continue
        if len(parts) == 1 and name in _EXCLUDED_ROOT_FILES:
            continue
        found.append((rel.as_posix(), p))
    found.sort(key=lambda t: t[0])
    return found


def _md5_of_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _companion_outputs(project_path: Path) -> list[str]:
    """Quines de `_COMPANION_OUTPUTS` existeixen ara mateix."""
    root = Path(project_path)
    return [rel for rel in _COMPANION_OUTPUTS if (root / rel).exists()]


def _user_data_signature(project_path: Path) -> str:
    ud = Path(project_path) / "user_data.json"
    if not ud.exists():
        return ""
    try:
        data = json.loads(ud.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "illegible"
    if not isinstance(data, dict):
        return "illegible"
    subset = {k: data[k] for k in _USER_DATA_INPUT_KEYS if k in data}
    return json.dumps(subset, sort_keys=True, ensure_ascii=False, default=str)


def inputs_fingerprint(project_path: str | Path) -> str:
    """md5 del contingut de tots els fitxers d'entrada + les claus de
    `user_data.json` que la Fase 3 llegeix. Determinista i independent de l'mtime."""
    root = Path(project_path)
    h = hashlib.md5()
    h.update(f"cache_version={CACHE_VERSION}\n".encode())
    for rel, path in _iter_input_files(root):
        try:
            digest = _md5_of_file(path)
        except OSError:
            digest = "unreadable"
        h.update(f"{rel}|{digest}\n".encode())
    h.update(f"user_data|{_user_data_signature(root)}\n".encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Serialització
# ---------------------------------------------------------------------------

def _is_pydantic(cls: Any) -> bool:
    return isinstance(cls, type) and hasattr(cls, "model_validate") and hasattr(cls, "model_fields")


def _to_jsonable(obj: Any) -> Any:
    """Converteix a JSON pur. Llança `TypeError` davant d'un tipus desconegut
    (millor no cachejar que cachejar una degradació silenciosa a `str`)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if _is_pydantic(type(obj)):
        return obj.model_dump(mode="json")
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (datetime,)) or hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"tipus no serialitzable a la cache: {type(obj).__name__}")


def _coerce(value: Any, hint: Any) -> Any:
    """Reconstrueix `value` (JSON pur) segons l'anotació de tipus `hint`."""
    if value is None:
        return None
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return _coerce(value, args[0]) if len(args) == 1 else value
    if origin is list:
        args = typing.get_args(hint)
        return [_coerce(v, args[0]) for v in value] if args else list(value)
    if origin is tuple:
        args = typing.get_args(hint)
        if not args:
            return tuple(value)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_coerce(v, args[0]) for v in value)
        return tuple(_coerce(v, a) for v, a in zip(value, args))
    if origin in (set, frozenset):
        args = typing.get_args(hint)
        inner = [_coerce(v, args[0]) for v in value] if args else list(value)
        return origin(inner)
    if origin is dict:
        args = typing.get_args(hint)
        vt = args[1] if len(args) == 2 else Any
        return {k: _coerce(v, vt) for k, v in value.items()}
    if isinstance(hint, type):
        if _is_pydantic(hint):
            return hint.model_validate(value)
        if dataclasses.is_dataclass(hint):
            return _dataclass_from_dict(hint, value)
    return value


def _dataclass_from_dict(cls: Any, data: Any, overrides: dict[str, Any] | None = None) -> Any:
    if not isinstance(data, dict):
        raise TypeError(f"s'esperava un dict per a {cls.__name__}, s'ha rebut {type(data).__name__}")
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue
        hint = (overrides or {}).get(f.name, hints.get(f.name, Any))
        kwargs[f.name] = _coerce(data[f.name], hint)
    return cls(**kwargs)


def _result_field_overrides() -> dict[str, Any]:
    """Tipus reals dels camps que `AutoExtractionResult` anota com a `Any`
    (`dpsh_data`, `lab_results`, …). Importació mandrosa: vegeu la capçalera.

    `mining_alternatives` NO hi és a posta: el comentari del camp diu
    `var → [Signal, ...]` però `auto_extractor.py` L.634 i L.748 hi posen
    dicts plans `{'value', 'source', 'confidence'}`. Ho va destapar el
    round-trip d'aquesta fase (`Signal.model_validate` fallant amb «Field
    required: type, label, source_file»). Es deixa com el que és — dicts
    plans — i el consumidor (`merged['_alternatives']`, badges +N del
    wizard) rep exactament el mateix que sense cache."""
    from automation.concept_scout.models import ConceptMap
    from automation.content_discovery import ContentDiscoveryResult
    from automation.dpsh_extractor import DPSHData
    from automation.file_scanner import FileMapping
    from automation.fileminer.models import MiningResult
    from automation.lab_extractor import LabResults

    return {
        "dpsh_data": DPSHData,
        "lab_results": LabResults,
        "file_mapping": FileMapping,
        "content_discovery": ContentDiscoveryResult,
        "mining_result": MiningResult,
        "concept_map": ConceptMap,
    }


def serialize(result: Any) -> dict:
    """`AutoExtractionResult` → dict JSON pur. Llança si algun camp no és serialitzable."""
    return {f.name: _to_jsonable(getattr(result, f.name)) for f in dataclasses.fields(result)}


def deserialize(data: dict) -> Any:
    """dict JSON pur → `AutoExtractionResult` amb els objectes niats reconstruïts."""
    from automation.auto_extractor import AutoExtractionResult
    return _dataclass_from_dict(AutoExtractionResult, data, overrides=_result_field_overrides())


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def load(project_path: str | Path) -> CachedRun | None:
    """Entrada vàlida de la cache, o `None` (desactivada, absent, versió vella,
    caducada, empremta diferent o il·legible). Mai llança."""
    if not is_enabled():
        return None
    path = cache_path(project_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("auto_result cache: entrada il·legible (%s) — es re-executa", exc)
        return None
    if not isinstance(data, dict) or data.get("cache_version") != CACHE_VERSION:
        logger.info("auto_result cache: versió diferent — es re-executa")
        return None

    saved_at = None
    raw_saved = data.get("saved_at")
    if isinstance(raw_saved, str):
        try:
            saved_at = datetime.fromisoformat(raw_saved)
        except ValueError:
            saved_at = None
    if saved_at is None:
        logger.info("auto_result cache: sense data de desat — es re-executa")
        return None
    age = datetime.now() - saved_at
    if age > timedelta(days=TTL_DAYS) or age < timedelta(0):
        logger.info("auto_result cache: caducada (%.1f dies) — es re-executa", age.total_seconds() / 86400)
        return None

    if data.get("inputs_md5") != inputs_fingerprint(project_path):
        logger.info("auto_result cache: els fitxers del projecte han canviat — es re-executa")
        return None

    missing = [rel for rel in (data.get("companions") or []) if not (Path(project_path) / rel).exists()]
    if missing:
        logger.info("auto_result cache: falten sortides del pipeline (%s) — es re-executa", ", ".join(missing))
        return None

    try:
        result = deserialize(data.get("result") or {})
    except Exception as exc:  # noqa: BLE001 — mai deixar l'Eva sense prefills
        logger.warning("auto_result cache: no s'ha pogut reconstruir (%s) — es re-executa", exc)
        return None

    events = [
        (e[0], e[1]) for e in (data.get("events") or [])
        if isinstance(e, list) and len(e) == 2 and isinstance(e[0], str) and isinstance(e[1], dict)
    ]
    logger.info(
        "auto_result cache: encert (%d prefills, %.1f dies, %d events)",
        len(getattr(result, "prefills", {})), age.total_seconds() / 86400, len(events),
    )
    return CachedRun(result=result, events=events, saved_at=saved_at, age_days=age.total_seconds() / 86400)


def save(
    project_path: str | Path,
    result: Any,
    events: list[tuple[str, dict]] | None = None,
) -> Path | None:
    """Desa `result` (escriptura atòmica). Retorna la ruta, o `None` si no s'ha
    desat. Mai llança: si la serialització falla, la propera càrrega serà freda.

    `events`: els events de progrés que `auto_extract` va emetre, per reproduir-los
    tal qual en un encert (la UI de TEMPS 1 no es pot quedar sense senyal només
    perquè la lectura hagi estat instantània)."""
    if not is_enabled():
        return None
    path = cache_path(project_path)
    try:
        payload = {
            "cache_version": CACHE_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "inputs_md5": inputs_fingerprint(project_path),
            "companions": _companion_outputs(project_path),
            "events": [[t, d] for t, d in (events or [])[:_MAX_EVENTS]],
            "result": serialize(result),
        }
        blob = json.dumps(payload, ensure_ascii=False, indent=1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto_result cache: no s'ha pogut serialitzar (%s) — no es desa", exc)
        return None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="._auto_result-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(blob)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError as exc:
        logger.warning("auto_result cache: no s'ha pogut escriure (%s)", exc)
        return None
    logger.info("auto_result cache: desada a %s (%d KB)", path, len(blob) // 1024)
    return path
