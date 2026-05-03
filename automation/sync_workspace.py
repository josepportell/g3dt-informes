"""Workflow còpia local + copy-back — producció v1 (2026-05-04).

Eva té projectes a una unitat de xarxa de G3DT (`F:\\projectes`). Per evitar
latència, conflictes amb altres usuaris, i carpetes de rastre (`validation/`,
JSONs, caches) als servidors compartits, el pipeline no toca mai la xarxa
durant l'execució: copia el projecte a `G3DT_LOCAL_WORKSPACE` i corre allà.
Només l'informe `.docx` final torna a la xarxa via `copyback_report`.

Activat quan **les dues** variables `G3DT_NETWORK_PROJECTS` i
`G3DT_LOCAL_WORKSPACE` estan configurades. Si no ho estan, fallback legacy:
el pipeline opera directament sobre `G3DT_PROJECTS_DIR` (mode dev/anterior).
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


def is_network_workflow_enabled() -> bool:
    """True si tant `G3DT_NETWORK_PROJECTS` com `G3DT_LOCAL_WORKSPACE` estan setejades."""
    return bool(config.G3DT_NETWORK_PROJECTS and config.G3DT_LOCAL_WORKSPACE)


def network_root() -> Path:
    return Path(config.G3DT_NETWORK_PROJECTS)


def workspace_root() -> Path:
    return Path(config.G3DT_LOCAL_WORKSPACE)


def workspace_project_path(project_name: str) -> Path:
    return workspace_root() / project_name


def list_network_projects() -> list[str]:
    """Enumera carpetes de primer nivell a la xarxa.

    Operació read-only sobre la xarxa: només llista noms, no obre fitxers.
    Resultat ordenat alfabèticament. Si la xarxa no és accessible, retorna [].
    """
    if not is_network_workflow_enabled():
        return []
    root = network_root()
    try:
        if not root.exists():
            logger.warning("Network root does not exist: %s", root)
            return []
        return sorted(d.name for d in root.iterdir() if d.is_dir())
    except (OSError, PermissionError) as exc:
        logger.warning("list_network_projects failed: %s", exc)
        return []


def sync_to_workspace(project_name: str, force: bool = False) -> dict:
    """Copia el projecte de la xarxa al workspace local.

    Idempotent: si la carpeta local ja existeix i `force=False`, salta sense
    copiar (Eva pot tornar a clicar el projecte sense recàrrega de xarxa).
    Si `force=True`, copia tot l'arbre per sobre (overwrite).

    Retorna un dict amb `status` ∈ {synced, skipped, error}.
    """
    if not is_network_workflow_enabled():
        return {"status": "skipped", "reason": "network workflow not enabled"}

    src = network_root() / project_name
    if not src.exists() or not src.is_dir():
        return {
            "status": "error",
            "error": f"project not found in network: {project_name}",
        }

    dst = workspace_project_path(project_name)
    if dst.exists() and not force:
        return {
            "status": "skipped",
            "reason": "already in workspace (use force=True to re-sync)",
            "destination": str(dst),
        }

    try:
        workspace_root().mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        files_copied = sum(1 for p in dst.rglob("*") if p.is_file())
        logger.info(
            "synced %s: %d files from %s to %s", project_name, files_copied, src, dst
        )
        return {
            "status": "synced",
            "files_copied": files_copied,
            "destination": str(dst),
        }
    except (OSError, shutil.Error) as exc:
        logger.exception("sync_to_workspace failed for %s", project_name)
        return {"status": "error", "error": str(exc)}


def copyback_report(project_name: str, docx_path: Path | str) -> dict:
    """Copia el `.docx` generat al directori original del projecte a la xarxa.

    Preserva el nom del fitxer (i timestamps via `shutil.copy2`). No esborra
    la còpia local — el `.docx` continua disponible a `G3DT_REPORTS_DIR`
    o on s'hagi generat.

    Retorna `status` ∈ {copied, skipped, error}.
    """
    if not is_network_workflow_enabled():
        return {"status": "skipped", "reason": "network workflow not enabled"}

    src = Path(docx_path)
    if not src.exists() or not src.is_file():
        return {"status": "error", "error": f"source docx not found: {docx_path}"}

    dst_dir = network_root() / project_name
    if not dst_dir.exists():
        return {
            "status": "error",
            "error": f"network project folder not found: {project_name}",
        }

    dst = dst_dir / src.name
    try:
        shutil.copy2(src, dst)
        logger.info("copied report back to network: %s", dst)
        return {"status": "copied", "destination": str(dst)}
    except (OSError, shutil.Error) as exc:
        logger.exception("copyback_report failed for %s", project_name)
        return {"status": "error", "error": str(exc)}
