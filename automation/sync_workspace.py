"""Workflow còpia local + copy-back — producció v1 (2026-05-04).

Eva té projectes a una unitat de xarxa de G3DT (`F:\\projectes`). Per evitar
latència, conflictes amb altres usuaris, i carpetes de rastre (`validation/`,
JSONs, caches) als servidors compartits, el pipeline no toca mai la xarxa
durant l'execució: copia el projecte a `G3DT_LOCAL_WORKSPACE` i corre allà.
Només l'informe `.docx` final torna a la xarxa via `copyback_report`.

Activat quan **les dues** variables `G3DT_NETWORK_PROJECTS` i
`G3DT_LOCAL_WORKSPACE` estan configurades. Si no ho estan, fallback legacy:
el pipeline opera directament sobre `G3DT_PROJECTS_DIR` (mode dev/anterior).

Nested folders (2026-05-06): `sync_to_workspace` accepta un *path relatiu*
des de `G3DT_NETWORK_PROJECTS` (ex: `2025/Lleida/4001612 BELL-LLOC`). El
nom de la carpeta fulla es manté com a identificador local del workspace
(ex: `4001612 BELL-LLOC`). Una col·lisió de noms fulla entre dos projectes
anidats diferents es resol afegint un suffix curt (`__a3f`). El path
relatiu original es desa al workspace (`.g3dt_network_path`) perquè
`copyback_report` sàpiga on retornar el `.docx`.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path, PurePosixPath

from . import config

logger = logging.getLogger(__name__)

# Marcador desat dins de cada workspace de projecte amb el path relatiu
# original a la xarxa. Permet a `copyback_report` retornar el `.docx` a la
# subcarpeta correcta encara que estigui anidada.
_NETWORK_PATH_MARKER = ".g3dt_network_path"


def is_network_workflow_enabled() -> bool:
    """True si tant `G3DT_NETWORK_PROJECTS` com `G3DT_LOCAL_WORKSPACE` estan setejades."""
    return bool(config.G3DT_NETWORK_PROJECTS and config.G3DT_LOCAL_WORKSPACE)


def network_root() -> Path:
    return Path(config.G3DT_NETWORK_PROJECTS)


def workspace_root() -> Path:
    return Path(config.G3DT_LOCAL_WORKSPACE)


def workspace_project_path(leaf_name: str) -> Path:
    return workspace_root() / leaf_name


def _normalize_rel_path(rel_path: str) -> PurePosixPath:
    """Normalitza un path relatiu a forma POSIX, sense `..` ni inici absolut.

    Tolerant amb separadors mixtes (Windows envia `\\`, web envia `/`).
    Retorna sempre un `PurePosixPath` per consistència interna.

    Rebutja amb `ValueError`:
    - Strings buits.
    - Paths absoluts (líder `/` o `\\`, o lletra d'unitat Windows com `C:`).
    - Components `..` o `.` (path traversal).
    - Caràcters NULL.
    """
    if not rel_path:
        raise ValueError("empty path")
    if "\x00" in rel_path:
        raise ValueError("null byte in path")
    stripped = rel_path.strip()
    if not stripped:
        raise ValueError("empty path")
    # Detecta absoluts ABANS d'unificar separadors
    if stripped.startswith(("/", "\\")):
        raise ValueError(f"absolute path not allowed: {rel_path!r}")
    # Lletra d'unitat Windows: "C:", "Z:\\", etc.
    if len(stripped) >= 2 and stripped[1] == ":" and stripped[0].isalpha():
        raise ValueError(f"absolute path not allowed: {rel_path!r}")
    cleaned = stripped.replace("\\", "/").strip("/")
    if not cleaned:
        raise ValueError("empty path")
    # Detecta `..` o `.` a la string crua (PurePosixPath els col·lapsa)
    raw_parts = cleaned.split("/")
    for part in raw_parts:
        if part in ("", ".", ".."):
            raise ValueError(f"invalid path component: {part!r}")
    return PurePosixPath(*raw_parts)


def resolve_network_path(rel_path: str) -> Path:
    """Resol un path relatiu a la xarxa, validant que queda dins de `network_root()`.

    Llança `ValueError` si:
    - El path està buit o té components invàlids (`..`, `.`).
    - El path resolt no és descendent de `network_root()` (path traversal).

    Llança `FileNotFoundError` si el path resolt no existeix o no és carpeta.
    """
    norm = _normalize_rel_path(rel_path)
    root = network_root()
    candidate = root / Path(*norm.parts)

    # Validació path traversal: el path resolt ha de ser descendent de network_root
    try:
        root_resolved = root.resolve()
        cand_resolved = candidate.resolve()
        cand_resolved.relative_to(root_resolved)
    except (ValueError, OSError) as exc:
        raise ValueError(f"path escapes network root: {rel_path!r}") from exc

    if not candidate.exists():
        raise FileNotFoundError(f"path does not exist: {rel_path}")
    if not candidate.is_dir():
        raise FileNotFoundError(f"path is not a directory: {rel_path}")
    return candidate


def browse_network(rel_path: str = "") -> dict:
    """Llista subcarpetes d'una carpeta de la xarxa (1 nivell, no recursiu).

    Args:
        rel_path: Path relatiu des de `network_root()`. Cadena buida = arrel.

    Retorna un dict amb:
        - `current_path`: Path relatiu normalitzat (str, separador `/`)
        - `parent_path`: Path relatiu del pare, o None si som a l'arrel
        - `subdirs`: Llista ordenada de noms de subcarpetes (str)

    Errors (excepcions):
        - `RuntimeError` si el workflow de xarxa no està habilitat.
        - `ValueError` si el path és invàlid o intent de traversal.
        - `FileNotFoundError` si el path no existeix.
        - `PermissionError` si no es pot llegir la carpeta.
    """
    if not is_network_workflow_enabled():
        raise RuntimeError("network workflow not enabled")

    if rel_path:
        target = resolve_network_path(rel_path)
        norm = _normalize_rel_path(rel_path)
        current = norm.as_posix()
        parent = norm.parent.as_posix() if len(norm.parts) > 1 else ""
    else:
        target = network_root()
        if not target.exists():
            raise FileNotFoundError(f"network root does not exist: {target}")
        current = ""
        parent = None  # No parent at root

    try:
        subdirs = sorted(
            d.name for d in target.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
    except PermissionError:
        raise
    except OSError as exc:
        raise PermissionError(f"cannot read directory {target}: {exc}") from exc

    return {
        "current_path": current,
        "parent_path": parent,
        "subdirs": subdirs,
    }


def _short_hash(rel_path: str) -> str:
    """Hash curt (3 chars) per a desambiguar leaf names duplicats."""
    return hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:3]


# Patrons que identifiquen una carpeta de projecte G3DT. Tots case-insensitive
# via implementació pròpia (no fem servir glob amb tots els case-permutations
# perquè és massa propens a oblidar-ne algun).
_PROJECT_FILE_PATTERNS = (
    "PENETROS",         # PENETROS.pdf, PENETROS + SONDEIGS.pdf, etc.
    "A.01",             # A.01.pdf, A.01 amb punts.pdf
    "SONDEIG",          # SONDEIG.pdf
)
# Subcarpetes on típicament viu el DPSH Excel
_DPSH_CONTAINERS = ("ANNEXES", "ANEXOS")


def _has_pattern_file(folder: Path, name_substring: str, suffix: str = ".pdf") -> bool:
    """Cerca al primer nivell de `folder` un fitxer amb `name_substring` (case-insensitive)
    i `suffix` (case-insensitive)."""
    sub_lower = name_substring.lower()
    suf_lower = suffix.lower()
    try:
        for p in folder.iterdir():
            if not p.is_file():
                continue
            name_lower = p.name.lower()
            if sub_lower in name_lower and name_lower.endswith(suf_lower):
                return True
    except OSError:
        return False
    return False


def _has_dpsh_excel(folder: Path) -> bool:
    """Cerca un Excel DPSH a `folder` o a subcarpetes ANNEXES/ANEXOS."""
    candidates = [folder]
    for container in _DPSH_CONTAINERS:
        sub = folder / container
        if sub.is_dir():
            candidates.append(sub)
    for cand in candidates:
        try:
            for p in cand.iterdir():
                if not p.is_file():
                    continue
                name_lower = p.name.lower()
                if "dpsh" in name_lower and (
                    name_lower.endswith(".xls") or name_lower.endswith(".xlsx")
                ):
                    return True
        except OSError:
            continue
    return False


def _looks_like_project(folder: Path) -> bool:
    """True si la carpeta sembla un projecte G3DT (té algun marker típic).

    Markers acceptats (qualsevol n'hi ha prou):
    - DPSH Excel a l'arrel o a ANNEXES/ANEXOS
    - PENETROS*.pdf
    - A.01*.pdf
    - SONDEIG*.pdf
    """
    if not folder.is_dir():
        return False
    if _has_dpsh_excel(folder):
        return True
    for sub in _PROJECT_FILE_PATTERNS:
        if _has_pattern_file(folder, sub, ".pdf"):
            return True
    return False


def _has_subdirs(folder: Path) -> bool:
    """True si `folder` té com a mínim una subcarpeta immediata (no oculta).

    Operació barata (1 nivell, atura al primer hit). S'usa per detectar
    "contenidors" — carpetes per on Eva navega però que no són projectes.
    """
    if not folder.is_dir():
        return False
    try:
        for child in folder.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                return True
    except OSError:
        return False
    return False


def _read_marker(workspace_path: Path) -> str | None:
    """Llegeix el marcador `.g3dt_network_path` o retorna None si no existeix."""
    marker = workspace_path / _NETWORK_PATH_MARKER
    if not marker.is_file():
        return None
    try:
        return marker.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_marker(workspace_path: Path, rel_path: str) -> None:
    """Desa el marcador `.g3dt_network_path` amb el path relatiu original."""
    marker = workspace_path / _NETWORK_PATH_MARKER
    marker.write_text(rel_path, encoding="utf-8")


def _resolve_workspace_leaf(rel_path: str) -> str:
    """Determina el nom local del workspace per a un projecte de la xarxa.

    Per defecte = nom de la carpeta fulla del path relatiu. Si ja existeix
    un workspace amb aquest mateix nom **però apuntant a un path diferent**
    (col·lisió), afegeix un suffix curt amb hash del path relatiu.

    No crea res; només calcula el nom.
    """
    norm = _normalize_rel_path(rel_path)
    leaf = norm.parts[-1]
    candidate = workspace_root() / leaf

    if candidate.exists():
        existing = _read_marker(candidate)
        # Si no hi ha marcador (workspace vell, pre-nested-folders): tractem
        # com a "el nom de la carpeta = el path original" (compat enrere).
        # Si el marker hi és i coincideix: és el mateix projecte, retornem leaf.
        if existing is None or existing == norm.as_posix():
            return leaf
        # Col·lisió real: afegim suffix
        return f"{leaf}__{_short_hash(norm.as_posix())}"

    return leaf


def sync_to_workspace(rel_path: str, force: bool = False, allow_no_markers: bool = False) -> dict:
    """Copia un projecte de la xarxa al workspace local.

    Args:
        rel_path: Path relatiu des de `network_root()`. Pot ser un nom plà
            (`4001612 BELL-LLOC`, compat enrere) o un path anidat
            (`2025/Lleida/4001612 BELL-LLOC`).
        force: Si True, re-copia per sobre encara que ja existeixi al
            workspace.
        allow_no_markers: Si True, salta el soft-block (`not_a_project`).
            S'usa quan Eva ha confirmat explícitament a la UI que vol
            continuar tot i que la carpeta no té marcadors típics de
            projecte (cas: projecte just començat sense DPSH).

    Validació pre-còpia (només si rel_path té components — la drecera
    idempotent salta aquesta validació per evitar re-comprovar al workspace):

    - Si la carpeta seleccionada conté ≥2 subcarpetes immediates que semblen
      projectes (DPSH/PENETROS/A.01), es rebutja amb `code="multi_project_container"`.
      No hi ha override: una crida a `copytree` aquí copiaria milers de
      fitxers innecessaris.
    - Si la carpeta no té cap marcador típic de projecte i
      `allow_no_markers=False`, es rebutja amb `code="not_a_project"`.
      Eva pot fer override des del frontend si sap que és un projecte vàlid
      en preparació.

    Retorna un dict amb:
        - `status`: "synced" | "skipped" | "error"
        - `leaf`: Nom de la carpeta local (identificador per a la resta del
          pipeline). Sempre present excepte en errors molt primerencs.
        - `network_path`: Path relatiu a la xarxa (ressende lectura del marker).
        - `code` (només quan `status="error"`): codi machine-readable per
          al frontend (`multi_project_container`, `not_a_project`, ...).
        - Camps específics segons `status`.
    """
    if not is_network_workflow_enabled():
        return {"status": "skipped", "reason": "network workflow not enabled"}

    # Cas especial: clic "Començar" a l'arrel (sense haver navegat enlloc).
    # Donem el mateix missatge amigable que per als grups intermedis enlloc
    # del críptic "empty path".
    if not rel_path or not rel_path.strip().strip("/").strip("\\"):
        return {
            "status": "error",
            "code": "multi_project_container",
            "error": (
                "Estàs a l'arrel de la xarxa. Navega fins a la carpeta del "
                "projecte que vols generar i prem Començar."
            ),
        }

    try:
        norm = _normalize_rel_path(rel_path)
    except ValueError as exc:
        return {"status": "error", "error": f"invalid path: {exc}"}

    rel_str = norm.as_posix()

    # Drecera idempotent: si l'input és UN sol component (un leaf) i ja
    # tenim un workspace amb marker per aquest leaf, fem skip sense tocar
    # la xarxa. Aquest cas el dispara `/api/prefills/<leaf>` quan ja s'ha
    # cridat `/api/network/select` amb el path complet anidat.
    # Important: només aplica si l'input NO té slashes — un path complet
    # (anidat) sempre s'ha de resoldre correctament contra la xarxa per
    # detectar col·lisions de leaf.
    if len(norm.parts) == 1 and not force:
        leaf_from_input = norm.parts[0]
        candidate_workspace = workspace_root() / leaf_from_input
        if candidate_workspace.exists():
            marker_value = _read_marker(candidate_workspace)
            if marker_value:
                return {
                    "status": "skipped",
                    "reason": "already in workspace (idempotent re-call)",
                    "leaf": leaf_from_input,
                    "network_path": marker_value,
                    "destination": str(candidate_workspace),
                }

    try:
        src = resolve_network_path(rel_str)
    except (ValueError, FileNotFoundError) as exc:
        return {"status": "error", "error": str(exc)}

    # Validació pre-còpia: evita el desastre de copiar contenidors per on
    # Eva navega (arrel, grups L1/L2, etc.) o carpetes que clarament no
    # són projectes (clic al lloc equivocat).
    if not _looks_like_project(src):
        # No té cap marker. És un contenidor o una carpeta no relacionada?
        if _has_subdirs(src):
            # Té subcarpetes → és un contenidor, NO copiem (podrien ser GBs).
            # Sense override possible: aquí Eva sempre s'equivoca.
            return {
                "status": "error",
                "code": "multi_project_container",
                "error": (
                    "Aquesta carpeta conté altres carpetes — sembla un "
                    "contenidor d'organització, no un projecte concret. "
                    "Navega fins a la carpeta del projecte que vols generar."
                ),
            }
        # Sense subcarpetes ni markers: sospitós però potser intencional
        # (projecte just començat). Eva pot fer override.
        if not allow_no_markers:
            return {
                "status": "error",
                "code": "not_a_project",
                "error": (
                    "Aquesta carpeta no té els fitxers típics d'un projecte "
                    "(cap DPSH, A.01, PENETROS o SONDEIG). Si saps que és un "
                    "projecte vàlid en preparació, pots continuar igualment."
                ),
            }

    leaf = _resolve_workspace_leaf(rel_str)
    dst = workspace_root() / leaf

    if dst.exists() and not force:
        # Idempotent skip — però assegurem que el marker és correcte
        existing = _read_marker(dst)
        if existing != rel_str:
            try:
                _write_marker(dst, rel_str)
            except OSError as exc:
                logger.warning("could not refresh marker for %s: %s", dst, exc)
        return {
            "status": "skipped",
            "reason": "already in workspace (use force=True to re-sync)",
            "leaf": leaf,
            "network_path": rel_str,
            "destination": str(dst),
        }

    try:
        workspace_root().mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        _write_marker(dst, rel_str)
        files_copied = sum(1 for p in dst.rglob("*") if p.is_file())
        logger.info(
            "synced %s: %d files from %s to %s", rel_str, files_copied, src, dst
        )
        return {
            "status": "synced",
            "leaf": leaf,
            "network_path": rel_str,
            "files_copied": files_copied,
            "destination": str(dst),
        }
    except (OSError, shutil.Error) as exc:
        logger.exception("sync_to_workspace failed for %s", rel_str)
        return {"status": "error", "error": str(exc), "leaf": leaf}


def copyback_report(leaf_name: str, docx_path: Path | str) -> dict:
    """Copia el `.docx` generat a la subcarpeta original del projecte a la xarxa.

    Llegeix el marcador `.g3dt_network_path` desat per `sync_to_workspace` per
    saber el path relatiu correcte (que pot ser anidat). Si no hi ha marker
    (compat enrere amb workspaces creats abans del 2026-05-06), assumeix que
    `leaf_name` és també el nom de la carpeta a l'arrel de la xarxa.

    Retorna `status` ∈ {copied, skipped, error}.
    """
    if not is_network_workflow_enabled():
        return {"status": "skipped", "reason": "network workflow not enabled"}

    src = Path(docx_path)
    if not src.exists() or not src.is_file():
        return {"status": "error", "error": f"source docx not found: {docx_path}"}

    workspace_path = workspace_project_path(leaf_name)
    rel_str = _read_marker(workspace_path)
    if rel_str is None:
        # Compat enrere: assumim path plà
        rel_str = leaf_name

    try:
        dst_dir = resolve_network_path(rel_str)
    except (ValueError, FileNotFoundError) as exc:
        return {
            "status": "error",
            "error": f"network project folder not found: {rel_str} ({exc})",
        }

    dst = dst_dir / src.name
    try:
        shutil.copy2(src, dst)
        logger.info("copied report back to network: %s", dst)
        return {"status": "copied", "destination": str(dst), "network_path": rel_str}
    except (OSError, shutil.Error) as exc:
        logger.exception("copyback_report failed for %s", rel_str)
        return {"status": "error", "error": str(exc)}
