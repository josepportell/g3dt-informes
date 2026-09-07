"""
FastAPI router with all API endpoints for the G3DT web wizard.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from automation import config
from automation.lectura import jobs as lectura_jobs

from . import wizard_service
from . import vision_fast

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# --- Production v1 (2026-05-04) feature-flag guards ---------------------------

def _require_ai_pipeline_enabled() -> None:
    """Block /api/ai-pipeline/* endpoints when AI pipeline is not enabled.

    Returns 404 (not 403) so the existence of these experimental endpoints
    is not advertised in production.
    """
    if not config.G3DT_ENABLE_AI_PIPELINE:
        raise HTTPException(status_code=404, detail="Not Found")


def _require_lectura_enabled() -> None:
    """Block `/api/lectura-stream/*` when the headless lectura pipeline is off.

    Returns 404 (not 403), same reasoning as `_require_ai_pipeline_enabled`:
    the existence of this experimental endpoint is not advertised in production.
    """
    if not config.G3DT_USE_LECTURA_HEADLESS:
        raise HTTPException(status_code=404, detail="Not Found")


def _require_claudecode_vision_enabled() -> None:
    """Block subprocess-based Claude CLI vision when not explicitly enabled.

    Default: false (Eva's machine has no Claude Code installed). Activated by
    setting `G3DT_PROD_USE_CLAUDECODE_VISION=true` in .env (independent of
    DEV_MODE). When in DEV_MODE we also allow it for local development.
    """
    if not (config.G3DT_PROD_USE_CLAUDECODE_VISION or config.G3DT_DEV_MODE):
        raise HTTPException(
            status_code=403,
            detail=(
                "Vision via Claude Code subprocess is disabled in this deployment. "
                "Set G3DT_PROD_USE_CLAUDECODE_VISION=true to enable."
            ),
        )


# --- Request/response models ---

class WizardSaveRequest(BaseModel):
    wizard_fields: dict[str, Any]
    expert_overrides: dict[str, Any] | None = None
    #: Fase 8b — tries d'Eva sobre cel·les de taula de la lectura
    #: (`"{bloc}.{index}.{cel·la}"`) i sobre camps de lectura sense input al
    #: wizard. Absent a la via B i als clients antics.
    lectura_selections: dict[str, Any] | None = None


class TargetedExtractRequest(BaseModel):
    """Request body for /wizard/{project}/extract-targeted."""

    concept_ids: list[str]
    upload_id: str | None = None
    file_path: str | None = None  # Relative to project root; path traversal rejected.


class GenerateResponse(BaseModel):
    success: bool
    output_name: str | None = None
    errors: list[str] = []
    warnings: list[str] = []


class AuditResponse(BaseModel):
    success: bool
    output_name: str | None = None
    auto_resolved_pct: float = 0
    needs_review: int = 0
    missing: int = 0
    errors: list[str] = []
    warnings: list[str] = []


# --- Endpoints ---

@router.get("/projects")
def list_projects():
    """List available projects from reference-material/."""
    return wizard_service.list_projects()


# --- Network browser (nested folders, 2026-05-06) ---------------------------
#
# Eva agrupa els projectes a la xarxa de G3DT en múltiples nivells (per any,
# zona, oficina). El dropdown legacy només llegia el primer nivell. Aquests
# endpoints permeten que el frontend mostri un navegador on Eva baixa per
# l'arbre fins a la carpeta del projecte i clica "Començar".

class NetworkSelectRequest(BaseModel):
    path: str
    refresh: bool = False
    allow_no_markers: bool = False


@router.get("/network/browse")
def network_browse(path: str = ""):
    """Llista subcarpetes d'una carpeta de la xarxa (1 nivell, no recursiu).

    Query params:
        path: Path relatiu des de `G3DT_NETWORK_PROJECTS`. Buit = arrel.

    Resposta:
        {current_path, parent_path, subdirs}
        - parent_path = null si som a l'arrel.

    Errors:
        400 si el path és invàlid (path traversal, components `..`).
        403 si no es pot llegir la carpeta (permisos).
        404 si el path no existeix.
        501 si el workflow de xarxa no està habilitat.
    """
    from automation import sync_workspace
    try:
        return sync_workspace.browse_network(path)
    except RuntimeError:
        raise HTTPException(
            status_code=501,
            detail="Network workflow not enabled. Configura G3DT_NETWORK_PROJECTS.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"No tens permís per llegir aquesta carpeta: {exc}",
        )


@router.post("/network/select")
def network_select(req: NetworkSelectRequest):
    """Sincronitza un projecte de la xarxa al workspace local.

    Body:
        {path: "<rel_path>", refresh: bool}

    Resposta:
        {leaf, status, network_path, ...}
        - `leaf`: identificador per usar a la resta d'endpoints
          (`/api/prefills/<leaf>`, `/api/wizard/<leaf>`, etc.).

    Errors:
        400 si el path és invàlid.
        404 si el projecte no es troba a la xarxa.
        500 si la còpia falla.
        501 si el workflow de xarxa no està habilitat.
    """
    from automation import sync_workspace
    if not sync_workspace.is_network_workflow_enabled():
        raise HTTPException(
            status_code=501,
            detail="Network workflow not enabled. Configura G3DT_NETWORK_PROJECTS.",
        )

    result = sync_workspace.sync_to_workspace(
        req.path,
        force=req.refresh,
        allow_no_markers=req.allow_no_markers,
    )
    if result["status"] == "error":
        err = result.get("error", "sync failed")
        code = result.get("code")

        # Codis machine-readable: el frontend els interpreta per decidir si
        # pot oferir override (not_a_project) o ha de bloquejar dur
        # (multi_project_container).
        if code in ("multi_project_container", "not_a_project"):
            raise HTTPException(
                status_code=400,
                detail={"message": err, "code": code},
            )

        # Distingim errors d'usuari (path invàlid, no existeix) d'errors interns
        lowered = err.lower()
        if "invalid path" in lowered or "escapes network root" in lowered:
            raise HTTPException(status_code=400, detail=err)
        if "does not exist" in lowered or "not a directory" in lowered:
            raise HTTPException(status_code=404, detail=err)
        raise HTTPException(status_code=500, detail=err)

    return result


@router.post("/cancel/{project_name:path}")
def cancel_pipeline(project_name: str):
    """Atura el pipeline en curs d'un projecte (cooperatiu, best-effort).

    Marca el projecte com a cancel·lat. Les fases del pipeline consulten
    aquesta flag entre operacions: les ja en vol acaben, però les futures
    se salten. El client haurà de tancar la seva connexió SSE per veure
    immediatament l'efecte a la UI.

    Resposta immediata (no espera que el pipeline acabi).
    """
    wizard_service.mark_cancelled(project_name)
    return {"status": "cancellation_requested", "project": project_name}


@router.get("/ai-pipeline/inventory/{project_name:path}")
def ai_pipeline_inventory(project_name: str, refresh: bool = False):
    """AI pipeline Stage 1: folder inventory.

    Returns cached `validation/ai_inventory.json` unless `refresh=true`, in which case
    .msg attachments are re-materialized, the tree is re-walked, and the cache is
    overwritten.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from automation.ai_pipeline.inventory import (
        build_inventory,
        load_inventory,
        save_inventory,
    )

    if not refresh:
        cached = load_inventory(project_path)
        if cached is not None:
            return {"inventory": cached.model_dump(), "cached": True}

    inv = build_inventory(project_path)
    save_inventory(inv, project_path)
    return {"inventory": inv.model_dump(), "cached": False}


@router.get("/ai-pipeline/typology/{project_name:path}")
def ai_pipeline_typology(project_name: str, refresh: bool = False):
    """AI pipeline Stage 2: file typology + embedded-image extraction.

    Returns cached `validation/ai_typology.json` unless `refresh=true`, in which
    case files are re-introspected, images are re-extracted (with SHA256 dedup),
    and the cache is overwritten.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from automation.ai_pipeline.typology import (
        classify_project,
        load_typology,
        save_typology,
    )

    if not refresh:
        cached = load_typology(project_path)
        if cached is not None:
            return {"typology": cached.model_dump(), "cached": True}

    typ = classify_project(project_path)
    save_typology(typ, project_path)
    return {"typology": typ.model_dump(), "cached": False}


@router.get("/ai-pipeline/conversion/{project_name:path}")
def ai_pipeline_conversion(project_name: str, refresh: bool = False):
    """AI pipeline Stage 3: convert every useful file to LLM-ready artifacts.

    Returns cached `validation/ai_conversion.json` unless `refresh=true`, in
    which case PDFs, DOCXs, Excels and .msg files are re-converted (with SHA256
    dedup), and the cache is overwritten.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from automation.ai_pipeline.conversion import (
        convert_project,
        load_conversion,
        save_conversion,
    )

    if not refresh:
        cached = load_conversion(project_path)
        if cached is not None:
            return {"conversion": cached.model_dump(), "cached": True}

    conv = convert_project(project_path)
    save_conversion(conv, project_path)
    return {"conversion": conv.model_dump(), "cached": False}


@router.get("/ai-pipeline/analysis/{project_name:path}")
def ai_pipeline_analysis(project_name: str, refresh: bool = False):
    """AI pipeline Stage 4: per-source LLM analysis.

    One multimodal call per source produces a SourceInsight + Candidate values.
    Per-source cache at validation/ai_pipeline/analysis/{stem}/_cache.json means
    unchanged sources return instantly at zero cost; `refresh=true` invalidates
    the top-level manifest but cache entries still short-circuit where inputs match.

    Returns systemic_failure set (and 200 OK with failure payload) when the API
    key is missing, credits are exhausted, or the model is not found.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from automation.ai_pipeline.analysis import (
        analyze_project,
        load_analysis,
        save_analysis,
    )

    if not refresh:
        cached = load_analysis(project_path)
        if cached is not None:
            return {"analysis": cached.model_dump(), "cached": True}

    analysis = analyze_project(project_path)
    save_analysis(analysis, project_path)
    return {"analysis": analysis.model_dump(), "cached": False}


@router.get("/ai-pipeline/ranking/{project_name:path}")
def ai_pipeline_ranking(
    project_name: str,
    refresh: bool = False,
    group_filter: str | None = None,
    no_group_pass: bool = False,
):
    """AI pipeline Stage 5: authority ranking per concept.

    Three-pass LLM pipeline (per-concept rank → per-group audit → targeted
    revision) producing an ordered candidate list per concept. Cached per-
    concept / per-group / per-revision; repeat requests hit cache at zero
    cost unless `refresh=true` or upstream inputs (principles text, glossary,
    concept definitions, Stage 4 candidates) changed.

    Returns systemic failure with 200 OK when the API key is missing,
    credits are exhausted, or the model is not found.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from automation.ai_pipeline.ranking import (
        rank_project,
        load_ranking,
        save_ranking,
    )

    if not refresh:
        cached = load_ranking(project_path)
        if cached is not None:
            return {"ranking": cached.model_dump(), "cached": True}

    gf: set[str] | None = None
    if group_filter:
        # allow comma-separated values for multi-group filter via single query param
        gf = {g.strip() for g in group_filter.split(",") if g.strip()}

    ranking = rank_project(
        project_path,
        group_filter=gf,
        no_group_pass=no_group_pass,
        force=refresh,  # refresh=true also bypasses the LLM per-call caches
    )
    save_ranking(ranking, project_path)
    return {"ranking": ranking.model_dump(), "cached": False}


@router.get("/ai-pipeline/trace/{project_name:path}")
def ai_pipeline_trace(project_name: str, refresh: bool = False):
    """AI pipeline diagnostic trace — read-only join over Stages 1-5.

    No LLM calls. Joins ai_inventory.json, ai_typology.json, ai_conversion.json,
    ai_analysis.json and ai_ranking.json into a unified PipelineTrace exposing
    per-concept journeys, per-source journeys, decision audits, cross-stage
    analyses, and a ranked top_issues list.

    Returns cached `validation/ai_pipeline_trace.json` unless `refresh=true`.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from automation.ai_pipeline.trace import (
        build_trace,
        load_trace,
        save_trace,
    )

    if not refresh:
        cached = load_trace(project_path)
        if cached is not None:
            return {"trace": cached.model_dump(), "cached": True}

    trace = build_trace(project_path)
    save_trace(trace, project_path)
    return {"trace": trace.model_dump(), "cached": False}


@router.get("/ai-pipeline/artifact/{project_name:path}")
def ai_pipeline_artifact(project_name: str, file: str):
    """Serve raw text (md/csv/json) AI pipeline artifacts for preview in the wizard.

    Only serves artifacts that live inside validation/ai_pipeline/ — under
    converted/ (Stage 3), analysis/ (Stage 4 cache) or ranking/ (Stage 5
    cache). Arbitrary project files are rejected. Large files are truncated
    at 200 KB.
    """
    _require_ai_pipeline_enabled()
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Path safety — must be inside validation/ai_pipeline/{converted,analysis,ranking}/
    resolved = (project_path / file).resolve()
    try:
        rel = resolved.relative_to(project_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    parts = rel.parts
    _allowed_subdirs = ("converted", "analysis", "ranking")
    if not (
        len(parts) >= 3
        and parts[0] == "validation"
        and parts[1] == "ai_pipeline"
        and parts[2] in _allowed_subdirs
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only AI pipeline artifacts under "
                f"validation/ai_pipeline/{{{','.join(_allowed_subdirs)}}}/ may be previewed"
            ),
        )
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    suffix = resolved.suffix.lower()
    if suffix not in (".md", ".csv", ".json"):
        raise HTTPException(status_code=415, detail=f"Preview not supported for {suffix}")

    MAX_BYTES = 200 * 1024
    data = resolved.read_bytes()
    truncated = len(data) > MAX_BYTES
    text = data[:MAX_BYTES].decode("utf-8", errors="replace")
    return {
        "path": rel.as_posix(),
        "size_bytes": len(data),
        "truncated": truncated,
        "content": text,
    }


@router.get("/prefills/{project_name:path}")
def get_prefills(project_name: str, refresh: bool = False):
    """Get auto-extracted + wizard prefills for a project.

    Production v1: if `G3DT_NETWORK_PROJECTS` is configured, syncs the
    project from the network share to `G3DT_LOCAL_WORKSPACE` before running
    the pipeline (idempotent — re-runs hit the local copy).
    """
    from automation import sync_workspace
    if sync_workspace.is_network_workflow_enabled():
        sync_result = sync_workspace.sync_to_workspace(project_name, force=refresh)
        if sync_result["status"] == "error":
            raise HTTPException(status_code=404, detail=sync_result.get("error", "sync failed"))

    try:
        return wizard_service.get_prefills(project_name, force_refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error getting prefills for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-data/{project_name:path}")
def get_user_data(project_name: str):
    """Read existing user_data.json for a project."""
    try:
        return wizard_service.load_user_data(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/prefills-stream/{project_name:path}")
def prefills_stream(project_name: str, refresh: bool = False):
    """SSE endpoint: streams progress events during extraction, then final prefills.

    Production v1: syncs from network share to local workspace first if
    `G3DT_NETWORK_PROJECTS` is configured (idempotent).

    `refresh=true` (botó «Actualitzar prefills») salta la cache de disc de la
    Fase 13(a). L'obertura normal d'un projecte NO el passa: hi encerta, i és
    el que estalvia els 43-141 s de tornar a fer l'extracció sencera.
    """
    from automation import sync_workspace
    if sync_workspace.is_network_workflow_enabled():
        sync_result = sync_workspace.sync_to_workspace(project_name, force=False)
        if sync_result["status"] == "error":
            raise HTTPException(status_code=404, detail=sync_result.get("error", "sync failed"))

    try:
        wizard_service._resolve_project(project_name)  # Validate project exists
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return StreamingResponse(
        wizard_service.get_prefills_streaming(project_name, force_refresh=refresh),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/lectura-stream/{project_name:path}")
def lectura_stream(project_name: str, attach: bool = False, refresh: bool = False):
    """SSE endpoint: headless `claude -p` lectura (via A) + auto_extract in
    parallel, then merged prefills. Gated by `G3DT_USE_LECTURA_HEADLESS`
    (404 when off — disseny §2/§9 Fase 5). Same media type/headers/style as
    `/api/prefills-stream` (via B, untouched).

    Fase 10 (`docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md`
    §5.2): `attach=false` (per defecte) arrenca un job nou o s'hi enganxa si
    ja n'hi ha un de viu — comportament idèntic a abans de la Fase 10.
    `attach=true` NOMÉS subscriu a un job JA viu (el job corre en un fil
    propi, no cal repetir el sync de xarxa ni la validació del projecte).

    `refresh=true` (botó «Actualitzar prefills») fa que el job nou salti la
    cache de disc de `_auto_extract_cached`. Només té efecte quan ARRENCA el
    job: enganxar-se a un que ja corre (o `attach=true`) no el pot rebobinar.
    L'obertura normal d'un projecte NO el passa — hi hem de seguir encertant.
    """
    _require_lectura_enabled()

    if not attach:
        from automation import sync_workspace
        if sync_workspace.is_network_workflow_enabled():
            sync_result = sync_workspace.sync_to_workspace(project_name, force=False)
            if sync_result["status"] == "error":
                raise HTTPException(status_code=404, detail=sync_result.get("error", "sync failed"))

        try:
            wizard_service._resolve_project(project_name)  # Validate project exists
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    from . import lectura_service

    return StreamingResponse(
        lectura_service.get_lectura_streaming(project_name, attach=attach, force_refresh=refresh),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/lectura/enabled")
def lectura_enabled():
    """Sonda de la UI (Fase 14a): la lectura headless està engegada?

    Existeix per no fer servir un 404 com a senyal. La resta d'endpoints
    d'aquest pipeline fan 404 amb el flag apagat, i està bé per a una API —
    però `fetch()` d'un 404 deixa una línia vermella a la consola del navegador
    encara que el codi el gestioni, i el criteri de la fase és **0 errors de
    consola** també amb el flag apagat, on la UI d'avui no ha de canviar en res.
    """
    return {"enabled": bool(config.G3DT_USE_LECTURA_HEADLESS)}


@router.get("/jobs")
def list_lectura_jobs(refresh: bool = False):
    """Taula d'estat dels jobs de lectura headless (Fase 10, disseny §5.2).

    `refresh=true` (botó *Actualitzar*, Fase 14b) torna a mirar la xarxa ara en
    lloc de servir el `network_delta` cachejat d'un minut. Segueix sent el mode
    `check` del delta-sync: no copia ni mou res, i no arrenca cap job.

    Gated per `G3DT_USE_LECTURA_HEADLESS` (404 quan és off, mateix criteri
    que la resta d'endpoints d'aquest pipeline).
    """
    _require_lectura_enabled()

    from . import lectura_service

    return {"jobs": lectura_service.list_jobs(refresh=refresh)}


@router.post("/jobs/{project_name:path}")
def start_lectura_job(project_name: str, button: str = "desde_zero"):
    """Arrenca (o s'enganxa a) un job de lectura headless per a un projecte
    (Fase 10, disseny §2/§3.4/§5.2).

    202 + `{"job": ..., "attach": false}` si crea un job nou. 409 +
    `{"job": ..., "attach": true}` si ja n'hi havia un de viu per aquest
    projecte — mai dos `run_lectura` del mateix projecte alhora.

    Totes dues respostes porten `"warnings"` (llista, buida quan tot ha anat bé)
    i, si n'hi ha, `"sync"` amb els indicadors del delta-sync
    (`scan_incomplete`/`mass_disappearance`/`scan_errors`/`vanished`).
    """
    _require_lectura_enabled()

    if button not in lectura_jobs.BUTTONS:
        raise HTTPException(status_code=400, detail=f"Botó desconegut: {button!r}")

    from automation import sync_workspace
    from . import lectura_service

    # Avisos del delta-sync cap a la pantalla de l'Eva (mateix contracte que el
    # `warnings` de `/api/generate`: cadenes ja redactades, informatives, que no
    # bloquegen res).
    warnings: list[str] = []
    sync_flags: dict = {}

    if sync_workspace.is_network_workflow_enabled():
        # Fase 11 (disseny §4, pas 1/4 dels botons 2 i 3): delta-sync en lloc de
        # la còpia idempotent. `sync_to_workspace(force=False)` feia `skipped`
        # quan el workspace ja existia, i el job es posava a llegir fitxers vells
        # sense dir-ho. Si el projecte encara no hi és, no hi ha delta possible:
        # còpia sencera com fins ara.
        delta = sync_workspace.sync_delta_for_leaf(project_name, check_only=False)
        if delta.get("status") == "error":
            raise HTTPException(status_code=404, detail=delta.get("error", "delta-sync failed"))
        if delta.get("status") in ("absent", "skipped"):
            sync_result = sync_workspace.sync_to_workspace(project_name, force=False)
            if sync_result["status"] == "error":
                raise HTTPException(status_code=404, detail=sync_result.get("error", "sync failed"))
        else:
            logger.info(
                "delta-sync %s: %d nous, %d canviats, %d apartats",
                project_name, len(delta.get("new") or []), len(delta.get("changed") or []),
                len(delta.get("deleted") or []),
            )
            # `status="ok"` amb `warning`: el delta-sync ha pres una decisió
            # prudent en silenci (escaneig de xarxa incomplet, o desaparició en
            # massa) i no ha apartat res. Si l'avís es queda al log del servidor,
            # l'Eva llegeix una còpia que pot ser incompleta sense saber-ho. El
            # text el redacta `sync_workspace` — diu què ha passat i què s'ha
            # fet, i no acusa la xarxa (pot haver reorganitzat ella la carpeta).
            if delta.get("warning"):
                warnings.append(delta["warning"])
                sync_flags = {
                    key: delta[key]
                    for key in ("scan_incomplete", "mass_disappearance", "scan_errors", "vanished")
                    if key in delta
                }
        lectura_service.invalidate_network_delta(project_name)

    try:
        wizard_service._resolve_project(project_name)  # Validate project exists
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    job, created = lectura_service.start_or_attach_job(project_name, button)
    body = {"job": job.snapshot(), "attach": not created, "warnings": warnings}
    if sync_flags:
        body["sync"] = sync_flags
    return JSONResponse(status_code=202 if created else 409, content=body)


@router.get("/pipeline-log/{project_name:path}")
def pipeline_log(project_name: str):
    """SSE endpoint: streams signal-level progress events during extraction."""
    import json as _json
    import queue
    import threading

    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    def generate():
        event_queue: queue.Queue = queue.Queue()

        def on_progress(event_type: str, detail: dict):
            event_queue.put((event_type, detail))

        def run_extract():
            try:
                from automation.auto_extractor import auto_extract
                auto_extract(project_path, on_progress=on_progress)
            except Exception as e:
                event_queue.put(("error", {"message": str(e)}))
            finally:
                event_queue.put(None)

        thread = threading.Thread(target=run_extract, daemon=True)
        thread.start()

        while True:
            item = event_queue.get()
            if item is None:
                yield f"event: done\ndata: {{}}\n\n"
                break
            event_type, detail = item
            yield f"event: {event_type}\ndata: {_json.dumps(detail, ensure_ascii=False)}\n\n"

        thread.join(timeout=5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class VisionStartRequest(BaseModel):
    force: bool = False


@router.post("/vision/{project_name:path}")
def start_vision(project_name: str, req: VisionStartRequest | None = None):
    """Start Claude CLI vision extraction for a project (non-blocking).

    Subprocess-based path that requires Claude Code installed locally.
    Disabled by default in production (G3DT_PROD_USE_CLAUDECODE_VISION=false).
    """
    _require_claudecode_vision_enabled()
    force = req.force if req else False
    try:
        result = wizard_service.start_vision_cli(project_name, force=force)
        status_code = 202 if result["status"] == "started" else 200
        return JSONResponse(content=result, status_code=status_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error starting vision for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vision-status/{project_name:path}")
def vision_status(project_name: str):
    """Check which vision extraction JSONs exist, their mtime, and process status."""
    try:
        file_status = wizard_service.get_vision_status(project_name)
        process_status = wizard_service.get_vision_process_status(project_name)
        return {**file_status, "_process": process_status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/vision-fast/{project_name:path}")
def start_vision_fast(project_name: str, req: VisionStartRequest | None = None):
    """Start fast vision extraction (claude -p from /tmp, no CLAUDE.md overhead)."""
    force = req.force if req else False
    try:
        project_path = wizard_service._resolve_project(project_name)
        result = vision_fast.start_vision_fast(
            project_name, project_path, wizard_service._PROJECT_ROOT, force=force
        )
        status_code = 202 if result["status"] == "started" else 200
        return JSONResponse(content=result, status_code=status_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error starting fast vision for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vision-fast-status/{project_name:path}")
def vision_fast_status(project_name: str):
    """Check fast vision extraction status and timing."""
    try:
        fast = vision_fast.get_fast_status(project_name)
        file_status = wizard_service.get_vision_status(project_name)
        return {**fast, "files": file_status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/wizard/{project_name:path}")
def save_wizard(project_name: str, req: WizardSaveRequest):
    """Save wizard data to user_data.json."""
    try:
        path = wizard_service.save_wizard(
            project_name, req.wizard_fields, req.expert_overrides,
            lectura_selections=req.lectura_selections,
        )
        return {"saved": True, "path": str(path)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error saving wizard for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/{project_name:path}", response_model=GenerateResponse)
def generate_report(project_name: str):
    """Generate the geotechnical report .docx.

    Production v1: if `G3DT_NETWORK_PROJECTS` is configured, copies the
    generated .docx back to the project's network folder. Failures in the
    copy-back are logged as warnings but do not block the response — Eva
    can still download the .docx from the wizard.
    """
    from automation import sync_workspace
    try:
        result = wizard_service.generate_report(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error generating report for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("success") and result.get("output_path"):
        if sync_workspace.is_network_workflow_enabled():
            cb = sync_workspace.copyback_report(project_name, result["output_path"])
            if cb["status"] == "error":
                logger.warning(
                    "Copy-back to network failed for %s: %s",
                    project_name, cb.get("error"),
                )
                result.setdefault("warnings", []).append(
                    f"Informe generat localment, però la còpia a la xarxa ha fallat: "
                    f"{cb.get('error')}"
                )
            elif cb["status"] == "copied":
                logger.info("Copied report to network: %s", cb.get("destination"))

    return GenerateResponse(**{k: v for k, v in result.items() if k in {
        "success", "output_name", "errors", "warnings"
    }})


class PhotoSelectionRequest(BaseModel):
    site_1: str | None = None
    site_2: str | None = None
    dpsh: str | None = None
    sondeig: str | None = None
    materials: str | None = None


class GeolocalitzarRequest(BaseModel):
    address: str | None = None


@router.post("/geolocalitzar/{project_name:path}")
def geolocalitzar(project_name: str, req: GeolocalitzarRequest | None = None):
    """Geocode project address to UTM coordinates."""
    try:
        address = req.address if req else None
        result = wizard_service.geocode_coords(project_name, address)
        return {
            "utm_x": round(result["utm_x"], 2),
            "utm_y": round(result["utm_y"], 2),
            "rc": result.get("rc"),
            "source": result.get("source", "geocode"),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Error geocoding %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{project_name:path}")
def download_report(project_name: str):
    """Download the generated .docx report."""
    try:
        report_path = wizard_service.find_report(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not report_path or not report_path.exists():
        raise HTTPException(status_code=404, detail="Informe no trobat. Genera'l primer.")

    return FileResponse(
        path=str(report_path),
        filename=report_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# --- Evidence endpoint (ortho chips for wizard panel) ---

@router.get("/evidence/{project_name:path}")
def get_evidence(project_name: str):
    """Return ortho enrichment evidence images as base64 for the wizard panel."""
    import base64

    try:
        prefills = wizard_service.get_prefills(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        return JSONResponse(content={})

    result: dict[str, Any] = {"tight_chip": None, "wide_chip": None, "strips": {}}

    def _encode(path_str: str | None) -> str | None:
        if not path_str:
            return None
        p = Path(path_str)
        if not p.exists():
            return None
        suffix = p.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        try:
            data = p.read_bytes()
            return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        except Exception as exc:
            logger.warning("Evidence encode failed for %s: %s", path_str, exc)
            return None

    # Extract paths from prefills (stored as {value, source} dicts)
    def _val(key: str) -> str | None:
        entry = prefills.get(key)
        if isinstance(entry, dict):
            return entry.get("value")
        return entry

    result["tight_chip"] = _encode(_val("_ortho_tight_chip"))
    result["wide_chip"] = _encode(_val("_ortho_wide_chip"))
    for direction in ("north", "south", "east", "west"):
        encoded = _encode(_val(f"_ortho_strip_{direction}"))
        if encoded:
            result["strips"][direction] = encoded

    # Only return data if there's at least one image
    if not result["tight_chip"] and not result["wide_chip"] and not result["strips"]:
        return JSONResponse(content={})

    return JSONResponse(content=result)


# --- Thumbnail endpoint ---

_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}


@router.get("/thumbnail/{project_name:path}")
def get_thumbnail(project_name: str, file: str, size: int = 80):
    """Serve a thumbnail of an image file from a project folder."""
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Security: prevent path traversal
    file_path = (project_path / file).resolve()
    if not str(file_path).startswith(str(project_path.resolve())):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if file_path.suffix.lower() not in _IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not an image file")

    # Generate thumbnail in memory
    try:
        from PIL import Image
        import io

        img = Image.open(str(file_path))
        img.thumbnail((size, size))
        buf = io.BytesIO()
        fmt = 'PNG' if file_path.suffix.lower() == '.png' else 'JPEG'
        img.save(buf, format=fmt, quality=75)
        img.close()
        buf.seek(0)

        media_type = 'image/png' if fmt == 'PNG' else 'image/jpeg'
        return StreamingResponse(buf, media_type=media_type)
    except Exception as e:
        logger.warning("Thumbnail generation failed for %s: %s", file, e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Figure preview endpoint ---

_FIGURE_CACHE_DIR = config.cache_dir("images")
_G3DT_ROOT = Path(__file__).resolve().parent.parent

# Prefix patterns in cache dir → figure slot key
_CACHE_PREFIX_TO_SLOT: list[tuple[str, str, str]] = [
    # (glob prefix, slot_key, human source label)
    ("cadastre_sitplan_*", "fig_cadastre", "PDF crop situation plan"),
    ("cadastre_*", "fig_cadastre", "Architect plan crop"),
    ("main_plan_*", "fig_main_plan", "Architect plan crop"),
    ("planol_*", "fig_main_plan", "Full plan render"),
    ("geological_composite_*", "fig_geological", "ICGC geological composite"),
    ("geological_*", "fig_geological", "ICGC geological map"),
    ("tall_*", "fig_correlation", "Correlation section PDF"),
]

# SmartScan role → figure slot key
_ROLE_TO_FIGURE_SLOT: dict[str, tuple[str, str]] = {
    "figure_situation_map": ("fig_cadastre", "SmartScan figure"),
    "figure_geological_map": ("fig_geological", "SmartScan figure"),
    "figure_test_points": ("fig_test_points", "SmartScan figure"),
    "figure_correlation": ("fig_correlation", "SmartScan figure"),
}


def _collect_figure_previews(
    project_path: Path, project_name: str
) -> dict[str, dict[str, str]]:
    """
    Collect figure image previews from cache, SmartScan roles, and static assets.

    Returns: {slot_key: {filename, thumbnail_url, source}} for each found figure.
    """
    import json as _json

    figures: dict[str, dict[str, str]] = {}
    encoded_name = quote(project_name, safe='')

    # 1. Scan cache dir for known prefixes
    if _FIGURE_CACHE_DIR.is_dir():
        for glob_prefix, slot_key, source_label in _CACHE_PREFIX_TO_SLOT:
            if slot_key in figures:
                continue  # first match wins per slot
            matches = sorted(_FIGURE_CACHE_DIR.glob(glob_prefix))
            if matches:
                f = matches[-1]  # most recent by name
                if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS:
                    figures[slot_key] = {
                        "filename": f.name,
                        "thumbnail_url": (
                            f"/api/figure-preview/{encoded_name}"
                            f"?slot={slot_key}&file={quote(f.name, safe='')}"
                        ),
                        "source": source_label,
                    }

    # 2. SmartScan figure roles from file_mapping.json
    fm_path = project_path / "file_mapping.json"
    if fm_path.exists():
        try:
            fm = _json.loads(fm_path.read_text(encoding="utf-8"))
            roles = fm.get("roles", {})
            for role_name, (slot_key, source_label) in _ROLE_TO_FIGURE_SLOT.items():
                if slot_key in figures:
                    continue
                if role_name in roles:
                    fig_file = project_path / roles[role_name]["path"]
                    if fig_file.exists() and fig_file.suffix.lower() in _IMAGE_EXTENSIONS:
                        rel = str(fig_file.relative_to(project_path))
                        figures[slot_key] = {
                            "filename": fig_file.name,
                            "thumbnail_url": (
                                f"/api/thumbnail/{encoded_name}"
                                f"?file={quote(rel, safe='/')}"
                            ),
                            "source": source_label,
                        }
        except Exception as e:
            logger.warning("Failed to read file_mapping.json for figures: %s", e)

    # 3. Static cullera SPT image
    if "fig_spt_cullera" not in figures:
        for ext in (".jpg", ".png"):
            p = _G3DT_ROOT / "templates" / "images" / f"cullera_spt{ext}"
            if p.exists():
                figures["fig_spt_cullera"] = {
                    "filename": p.name,
                    "thumbnail_url": (
                        f"/api/figure-preview/{encoded_name}"
                        f"?slot=fig_spt_cullera&file={quote(p.name, safe='')}"
                    ),
                    "source": "Static template",
                }
                break

    return figures


@router.get("/figure-preview/{project_name:path}")
def get_figure_preview(project_name: str, slot: str, file: str, size: int = 200):
    """Serve a thumbnail of a figure image from cache or static assets."""
    # Validate project exists (security: only serve for valid projects)
    try:
        wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Resolve figure file: check cache dir first, then static templates
    file_path: Path | None = None
    candidate = (_FIGURE_CACHE_DIR / file).resolve()
    if candidate.is_file() and str(candidate).startswith(str(_FIGURE_CACHE_DIR.resolve())):
        file_path = candidate

    if file_path is None:
        candidate = (_G3DT_ROOT / "templates" / "images" / file).resolve()
        templates_dir = (_G3DT_ROOT / "templates" / "images").resolve()
        if candidate.is_file() and str(candidate).startswith(str(templates_dir)):
            file_path = candidate

    if file_path is None:
        raise HTTPException(status_code=404, detail="Figure file not found")

    if file_path.suffix.lower() not in _IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not an image file")

    try:
        from PIL import Image
        import io

        img = Image.open(str(file_path))
        img.thumbnail((size, size))
        buf = io.BytesIO()
        fmt = "PNG" if file_path.suffix.lower() == ".png" else "JPEG"
        img.save(buf, format=fmt, quality=75)
        img.close()
        buf.seek(0)

        media_type = "image/png" if fmt == "PNG" else "image/jpeg"
        return StreamingResponse(buf, media_type=media_type)
    except Exception as e:
        logger.warning("Figure thumbnail generation failed for %s: %s", file, e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Photo picker endpoints ---

_PHOTO_SLOTS = {
    "site_1": {"category": "site", "label": "Vista general 1"},
    "site_2": {"category": "site", "label": "Vista general 2"},
    "dpsh": {"category": "dpsh", "label": "DPSH"},
    "sondeig": {"category": "sondeig", "label": "Sondeig"},
    "materials": {"category": "materials", "label": "Materials"},
}


@router.get("/photos/{project_name:path}")
def list_photos(project_name: str):
    """List candidate photos and current selection for a project."""
    import json as _json

    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Find photos directory
    foto_dir: Path | None = None
    for name in ['FOTOGRAFIES', 'FOTOS DE CAMP + PLANOL PUNTS', 'FOTOGRAFÍAS']:
        candidate = project_path / name
        if candidate.is_dir():
            foto_dir = candidate
            break
    if foto_dir is None:
        for d in sorted(project_path.iterdir()):
            if d.is_dir() and d.name.upper().startswith('FOTOS'):
                foto_dir = d
                break

    photos: list[dict[str, str]] = []
    if foto_dir:
        for f in sorted(foto_dir.rglob('*')):
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS and f.name != 'Thumbs.db':
                rel = str(f.relative_to(project_path))
                photos.append({
                    "filename": f.name,
                    "relative_path": rel,
                    "thumbnail_url": f"/api/thumbnail/{quote(project_name, safe='')}?file={quote(rel, safe='/')}",
                })

    # Load current selection
    sel_path = project_path / 'validation' / 'photo_selection.json'
    current_selection: dict[str, Any] | None = None
    if sel_path.exists():
        try:
            current_selection = _json.loads(sel_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    # Slot info for the frontend
    slot_info = {
        "site": {"count": 2, "label": "Vista general"},
        "dpsh": {"count": 1, "label": "DPSH"},
        "sondeig": {"count": 1, "label": "Sondeig"},
        "materials": {"count": 1, "label": "Materials"},
    }

    # Collect figure previews (cache, SmartScan, static)
    figures = _collect_figure_previews(project_path, project_name)

    return {
        "photos": photos,
        "figures": figures,
        "current_selection": current_selection,
        "slot_info": slot_info,
    }


@router.post("/photos/{project_name:path}/select")
def select_photos(project_name: str, req: PhotoSelectionRequest):
    """Save user photo selection for report generation."""
    import json as _json

    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    resolved_project = project_path.resolve()

    # Validate each path
    selection: dict[str, Any] = {"source": "user"}
    for slot in ("site_1", "site_2", "dpsh", "sondeig", "materials"):
        rel_path = getattr(req, slot)
        if rel_path is None:
            selection[slot] = None
            continue

        # Security: resolve and check within project
        file_path = (project_path / rel_path).resolve()
        if not str(file_path).startswith(str(resolved_project)):
            raise HTTPException(status_code=403, detail=f"Path traversal not allowed: {slot}")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {rel_path}")
        if file_path.suffix.lower() not in _IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Not an image file: {rel_path}")

        selection[slot] = rel_path

    sel_dir = project_path / 'validation'
    sel_dir.mkdir(exist_ok=True)
    sel_path = sel_dir / 'photo_selection.json'
    sel_path.write_text(_json.dumps(selection, indent=2, ensure_ascii=False), encoding='utf-8')

    return {"status": "saved"}


@router.post("/photos/{project_name:path}/reset")
def reset_photos(project_name: str):
    """Delete user photo selection, reverting to AI/auto selection."""
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    sel_path = project_path / 'validation' / 'photo_selection.json'
    if sel_path.exists():
        sel_path.unlink()

    return {"status": "reset"}


# --- SmartScan endpoints ---

@router.get("/smartscan/{project_name:path}")
def smartscan_get(project_name: str):
    """Run SmartScan classification (no extraction, fast)."""
    try:
        project_path = wizard_service._resolve_project(project_name)
        from automation.smartscan import scan_project
        result = scan_project(project_path, max_tier=2)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error running SmartScan for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smartscan/{project_name:path}")
def smartscan_post(project_name: str):
    """Run SmartScan classification + save file_mapping.json."""
    try:
        project_path = wizard_service._resolve_project(project_name)
        from automation.smartscan import scan_project
        result = scan_project(project_path, max_tier=2)

        # Save file_mapping.json for downstream compatibility
        import json
        fm = result.to_file_mapping()
        fm_path = project_path / 'file_mapping.json'
        fm_path.write_text(json.dumps(fm, indent=2, ensure_ascii=False), encoding='utf-8')

        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error running SmartScan for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


class SmartScanOverrideRequest(BaseModel):
    file_path: str
    role: str


@router.post("/smartscan-override/{project_name:path}")
def smartscan_override(project_name: str, req: SmartScanOverrideRequest):
    """Eva manually assigns a role to a file."""
    try:
        project_path = wizard_service._resolve_project(project_name)

        # Load current file_mapping, apply override, save
        fm_path = project_path / 'file_mapping.json'
        import json
        if fm_path.exists():
            fm = json.loads(fm_path.read_text(encoding='utf-8'))
        else:
            fm = {"roles": {}, "ignored": [], "unassigned": [], "_metadata": {}}

        from automation.file_scanner import get_vision_type
        fm["roles"][req.role] = {
            "path": req.file_path,
            "confidence": "high",
            "detection": "manual_override",
            "vision_type": get_vision_type(req.role),
        }

        # Remove from unassigned if present
        if req.file_path in fm.get("unassigned", []):
            fm["unassigned"].remove(req.file_path)

        fm_path.write_text(json.dumps(fm, indent=2, ensure_ascii=False), encoding='utf-8')

        return {"success": True, "role": req.role, "file_path": req.file_path}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error applying SmartScan override for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document-pages/{project_name:path}")
def get_document_pages(project_name: str, file: str = ""):
    """Get page count and metadata for a document (for format learning drawer)."""
    import fitz  # PyMuPDF

    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    file_path = project_path / file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file}")

    pages = 0
    if file_path.suffix.lower() == ".pdf":
        try:
            doc = fitz.open(str(file_path))
            pages = len(doc)
            doc.close()
        except Exception:
            pages = 0

    return {
        "file": file,
        "pages": pages,
        "role": "",  # Could look up from file_mapping
        "size_bytes": file_path.stat().st_size,
    }


@router.post("/audit/{project_name:path}", response_model=AuditResponse)
def run_audit(project_name: str):
    """Run intelligent audit: compare generated vs reference report."""
    try:
        result = wizard_service.run_audit_visual(project_name)
        return AuditResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error running audit for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-report/{project_name:path}")
def download_audit_report(project_name: str):
    """Download the AUDIT_VISUAL .docx."""
    try:
        report_path = wizard_service.find_audit_report(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not report_path or not report_path.exists():
        raise HTTPException(status_code=404, detail="Audit visual no trobat. Executa l'audit primer.")

    return FileResponse(
        path=str(report_path),
        filename=report_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# --- Groq Deep Mine endpoints ---

class GroqMineRequest(BaseModel):
    model: str = config.TEXT_MODEL_GROQ
    clear_cache: bool = False


@router.post("/groq-mine/{project_name:path}")
def groq_mine(project_name: str, req: GroqMineRequest | None = None):
    """Run Groq deep mine on a project with specified model."""
    import shutil

    model = req.model if req else config.TEXT_MODEL_GROQ
    clear_cache = req.clear_cache if req else False

    os.environ["G3DT_USE_GROQ"] = "1"
    os.environ["GROQ_MODEL"] = model

    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not set")

    if clear_cache:
        cache_dir = config.cache_dir("groq")
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("Groq cache cleared")

    try:
        project_path = wizard_service._resolve_project(project_name)

        from automation.fileminer.miners.groq_miner import GroqMiner
        GroqMiner.reset_counters()

        from automation.auto_extractor import auto_extract
        result = auto_extract(project_path, skip_phase3=True)

        usage = GroqMiner.get_usage_summary()

        groq_prefills = {
            k: {"value": v, "source": result.sources.get(k, "?")}
            for k, v in result.prefills.items()
            if result.sources.get(k, "").startswith("groq_llm:")
        }

        return {
            "model": model,
            "total_prefills": len(result.prefills),
            "groq_prefills": groq_prefills,
            "groq_count": len(groq_prefills),
            "all_prefills": {
                k: {"value": v, "source": result.sources.get(k, "?")}
                for k, v in sorted(result.prefills.items())
            },
            "usage": usage,
            "steps": result.steps_completed,
            "skipped": [{"step": s, "reason": r} for s, r in result.steps_skipped],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error running Groq mine for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groq-models")
def groq_models():
    """List available Groq models with pricing info."""
    return {
        "models": [
            {
                "id": "llama-3.1-8b-instant",
                "name": "Llama 3.1 8B Instant",
                "input_price_per_m": 0.05,
                "output_price_per_m": 0.08,
                "speed_tps": 840,
                "context_window": 131072,
                "notes": "Fastest, cheapest. Good for simple extractions.",
            },
            {
                "id": "qwen/qwen3-32b",
                "name": "Qwen3 32B",
                "input_price_per_m": 0.29,
                "output_price_per_m": 0.59,
                "speed_tps": 662,
                "context_window": 131072,
                "notes": "Strong multilingual (Catalan/Spanish). Mid-range.",
            },
            {
                "id": "llama-3.3-70b-versatile",
                "name": "Llama 3.3 70B Versatile",
                "input_price_per_m": 0.59,
                "output_price_per_m": 0.79,
                "speed_tps": 394,
                "context_window": 131072,
                "notes": "Most capable. Best accuracy, slower.",
            },
            {
                "id": "qwen/qwen3.6-27b",
                "name": "Qwen3.6 27B",
                "input_price_per_m": 0.60,
                "output_price_per_m": 3.00,
                "speed_tps": 500,
                "context_window": 131072,
                "notes": "Multimodal (text+vision). Replaces deprecated Llama 4 Scout (retired 2026-07-17).",
            },
        ],
        "current_model": os.environ.get("GROQ_MODEL", config.TEXT_MODEL_GROQ),
        "api_key_set": bool(os.environ.get("GROQ_API_KEY")),
    }


class SetModelRequest(BaseModel):
    model: str


@router.post("/groq-model")
def set_groq_model(req: SetModelRequest):
    """Set the Groq text miner model at runtime."""
    valid_models = {
        "llama-3.1-8b-instant", "qwen/qwen3-32b",
        "llama-3.3-70b-versatile", "qwen/qwen3.6-27b",
    }
    if req.model not in valid_models:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")
    os.environ["GROQ_MODEL"] = req.model
    return {"model": req.model, "status": "ok"}


@router.get("/dev-analysis/{project_name:path}")
def dev_analysis(project_name: str):
    """Dev analysis: breakdown of what each extraction subsystem found."""
    try:
        project_path = wizard_service._resolve_project(project_name)

        # Get current prefills (from cache if available)
        prefills = wizard_service.get_prefills(project_name)

        # Categorize by source
        categories = {
            "fileminer": {"label": "FileMiner (regex)", "icon": "search", "items": {}},
            "groq_llm": {"label": "Groq LLM", "icon": "brain", "items": {}},
            "contingut": {"label": "Content Discovery", "icon": "file", "items": {}},
            "vision": {"label": "Claude Vision", "icon": "eye", "items": {}},
            "icgc": {"label": "ICGC/Cadastre APIs", "icon": "map", "items": {}},
            "other": {"label": "Other sources", "icon": "info", "items": {}},
        }

        # All target variables we want to fill
        target_vars = [
            "architect_name", "architect_company", "client_name", "client_nif",
            "client_phone", "client_email", "client_address",
            "street_address", "site_municipality", "municipality", "province",
            "building_type", "num_floors",
            "superficie_construida_m2", "superficie_parcela_m2", "superficie_cadastral_m2",
            "building_height_m", "has_basement", "has_retaining_walls",
            "adjacent_north", "adjacent_south", "adjacent_east", "adjacent_west",
            "utm_x", "utm_y", "cota_referencia",
            "icgc_unit_code", "icgc_unit_description",
            "expedient", "field_date", "report_date",
            "access_url", "contact_name", "lab_company",
        ]

        filled = {}
        unfilled = []

        for var in target_vars:
            entry = prefills.get(var)
            if entry and isinstance(entry, dict) and entry.get("value"):
                source = entry.get("source", "unknown")
                value = entry["value"]

                # Categorize by source prefix
                if source.startswith("groq_llm:"):
                    cat = "groq_llm"
                elif source.startswith("fileminer:"):
                    cat = "fileminer"
                elif source.startswith("contingut:"):
                    cat = "contingut"
                elif "vision" in source or "planol" in source or "sondeig" in source:
                    cat = "vision"
                elif "ICGC" in source or "icgc" in source or "cadastre" in source or "geocode" in source:
                    cat = "icgc"
                elif source in ("nom carpeta", "defecte", "plantilla", "user"):
                    cat = "other"
                else:
                    cat = "other"

                categories[cat]["items"][var] = {
                    "value": str(value)[:100],
                    "source": source,
                }
                filled[var] = {"value": str(value)[:100], "source": source, "category": cat}
            else:
                unfilled.append(var)

        # Also check for alternatives
        alts = {}
        alt_entry = prefills.get("_alternatives")
        if alt_entry and isinstance(alt_entry, dict):
            alt_data = alt_entry.get("value", {})
            if isinstance(alt_data, dict):
                for var, alt_list in alt_data.items():
                    if isinstance(alt_list, list) and alt_list:
                        alts[var] = [
                            {"value": str(a.get("value", ""))[:80], "source": a.get("source", "?")}
                            for a in alt_list[:5]
                        ]

        return {
            "categories": {k: v for k, v in categories.items() if v["items"]},
            "filled_count": len(filled),
            "unfilled_count": len(unfilled),
            "unfilled": unfilled,
            "total_target": len(target_vars),
            "alternatives": alts,
            "coverage_pct": round(len(filled) / len(target_vars) * 100, 1) if target_vars else 0,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error in dev analysis for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dev-analysis-v2/{project_name:path}")
def dev_analysis_v2(project_name: str):
    """Enhanced dev analysis: full signal trace with winner/alternatives per variable."""
    try:
        # Ensure prefills are loaded (populates auto_result cache)
        wizard_service.get_prefills(project_name)
        auto_result = wizard_service.get_auto_result(project_name)
        if not auto_result or not auto_result.mining_result:
            raise HTTPException(
                status_code=400,
                detail="No mining data available. Load the project first.",
            )

        from automation.fileminer.competition import resolve_competition

        all_signals = auto_result.mining_result.signals
        resolved = resolve_competition(all_signals)

        # All target variables
        target_vars = [
            "architect_name", "architect_company", "client_name", "client_nif",
            "client_phone", "client_email", "client_address",
            "street_address", "site_municipality", "municipality", "province",
            "building_type", "num_floors",
            "superficie_construida_m2", "superficie_parcela_m2", "superficie_cadastral_m2",
            "building_height_m", "has_basement", "has_retaining_walls",
            "adjacent_north", "adjacent_south", "adjacent_east", "adjacent_west",
            "utm_x", "utm_y", "cota_referencia",
            "icgc_unit_code", "icgc_unit_description",
            "expedient", "field_date", "report_date",
            "access_url", "contact_name", "lab_company",
        ]

        # Build per-variable detail
        variables: dict[str, Any] = {}
        for var in target_vars:
            rv = resolved.get(var)
            if rv:
                variables[var] = {
                    "winner": {
                        "value": str(rv.signal.value)[:200],
                        "label": rv.signal.label,
                        "source_file": rv.signal.source_file,
                        "extraction_method": rv.signal.extraction_method,
                        "confidence": rv.signal.confidence,
                        "priority": rv.signal.priority,
                    },
                    "alternatives": [
                        {
                            "value": str(a.value)[:200],
                            "label": a.label,
                            "source_file": a.source_file,
                            "extraction_method": a.extraction_method,
                            "confidence": a.confidence,
                            "priority": a.priority,
                        }
                        for a in rv.alternatives
                    ],
                }
            else:
                variables[var] = None

        # Unmapped signals (maps_to is None, skip trivial labels)
        trivial_labels = {"msg_attachment", "embedded_image", "photo"}
        unmapped = [
            {
                "label": s.label,
                "value": str(s.value)[:200],
                "source_file": s.source_file,
                "extraction_method": s.extraction_method,
                "confidence": s.confidence,
            }
            for s in all_signals
            if s.maps_to is None and s.label not in trivial_labels
        ]

        # File contribution summary
        from collections import defaultdict
        file_stats: dict[str, dict] = defaultdict(lambda: {
            "signals_total": 0, "signals_mapped": 0,
            "variables_won": [], "variables_lost": [],
        })
        for s in all_signals:
            fs = file_stats[s.source_file]
            fs["signals_total"] += 1
            if s.maps_to is not None:
                fs["signals_mapped"] += 1
        for var, rv in resolved.items():
            fs = file_stats[rv.signal.source_file]
            if var not in fs["variables_won"]:
                fs["variables_won"].append(var)
            for a in rv.alternatives:
                afs = file_stats[a.source_file]
                if var not in afs["variables_lost"]:
                    afs["variables_lost"].append(var)

        files_summary = {
            f: {**stats} for f, stats in sorted(file_stats.items())
        }

        # Pipeline stage stats
        _FILEMINER_METHODS = {
            "label_value", "label_adjacent", "cell_adjacent", "cell_scan",
            "regex", "regex_phone", "regex_url", "regex_email",
            "msg_header", "msg_body", "msg_sender", "msg_attachment",
            "embedded_image",
        }

        def _classify_stage(method: str) -> str:
            if method.startswith("groq_"):
                return "groq_llm"
            if method in _FILEMINER_METHODS:
                return "fileminer"
            if method.startswith("contingut") or method == "content_discovery":
                return "content_discovery"
            if "icgc" in method or "cadastre" in method or "geocode" in method:
                return "icgc"
            if "vision" in method:
                return "vision"
            return "other"

        stage_stats: dict[str, dict] = defaultdict(lambda: {
            "signals": 0, "mapped": 0, "won": 0,
        })
        for s in all_signals:
            stage = _classify_stage(s.extraction_method)
            stage_stats[stage]["signals"] += 1
            if s.maps_to is not None:
                stage_stats[stage]["mapped"] += 1

        # Count wins per stage
        for var, rv in resolved.items():
            stage = _classify_stage(rv.signal.extraction_method)
            stage_stats[stage]["won"] += 1

        filled = sum(1 for v in variables.values() if v is not None)
        total = len(target_vars)

        # Final merged prefills: shows ALL sources including vision, ICGC, cadastre
        prefills = wizard_service.get_prefills(project_name)
        final_prefills = {}
        for k, v in sorted(prefills.items()):
            if k.startswith('_'):
                continue
            if not isinstance(v, dict):
                continue
            src = v.get('source', '?')
            val = v.get('value', '')
            # Skip complex objects (lists, dicts) — just show scalar values
            if isinstance(val, (list, dict)):
                val = f"[{type(val).__name__}: {len(val)} items]"
            else:
                val = str(val)[:150]
            final_prefills[k] = {"value": val, "source": src}

        # Classify final prefills by source type
        def _classify_source(src: str) -> str:
            if not src:
                return "other"
            sl = src.lower()
            if sl.startswith("groq_llm:"):
                return "groq_llm"
            if sl.startswith("fileminer:"):
                return "fileminer"
            if sl.startswith("contingut:"):
                return "content_discovery"
            if any(x in sl for x in ("icgc", "cadastre", "geocode")):
                return "icgc_cadastre"
            if any(x in sl for x in ("sondeig", "planol", "vision", "dpsh")):
                return "vision_field"
            if any(x in sl for x in ("plantilla", "default", "nom carpeta")):
                return "generated"
            if sl == "user":
                return "user"
            return "other"

        prefill_by_source: dict[str, int] = defaultdict(int)
        for v in final_prefills.values():
            cat = _classify_source(v["source"])
            prefill_by_source[cat] += 1

        return {
            "variables": variables,
            "unmapped_signals": unmapped,
            "files_summary": files_summary,
            "pipeline_stages": dict(stage_stats),
            "coverage": {
                "filled": filled,
                "unfilled": total - filled,
                "total": total,
                "pct": round(filled / total * 100, 1) if total else 0,
            },
            "final_prefills": final_prefills,
            "prefill_source_counts": dict(prefill_by_source),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error in dev analysis v2 for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api-capabilities")
def api_capabilities():
    """Report which API keys + feature flags are configured.

    Frontend uses this to render conditional UI (e.g. show/hide Claude Code
    vision button when G3DT_PROD_USE_CLAUDECODE_VISION is true).
    """
    import shutil
    return {
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "claude_cli": bool(shutil.which(os.environ.get("G3DT_CLAUDE_PATH", "claude"))),
        "vision_auto": bool(os.environ.get("GROQ_API_KEY")),
        "ai_pipeline_enabled": config.G3DT_ENABLE_AI_PIPELINE,
        "dev_mode": config.G3DT_DEV_MODE,
        "claudecode_vision_enabled": config.G3DT_PROD_USE_CLAUDECODE_VISION,
    }


# --- Report Readiness ---

# Curated list of report-critical template variables, grouped by category.
# These are the variables from report_generator._build_template_context()
# that must be filled for a complete report.
READINESS_VARIABLES: dict[str, list[dict]] = {
    "Identificacio": [
        {"key": "client", "label": "Client / Promotor"},
        {"key": "expedient", "label": "Expedient"},
        {"key": "architect_name", "label": "Arquitecte"},
        {"key": "architect_company", "label": "Despatx arquitecte"},
        {"key": "data_camp_text", "label": "Data de camp"},
        {"key": "data_signatura_text", "label": "Data signatura"},
    ],
    "Ubicacio": [
        {"key": "street_address", "label": "Adreca"},
        {"key": "municipality", "label": "Municipi"},
        {"key": "location_sentence", "label": "Frase ubicacio"},
        {"key": "adjacent_north", "label": "Limita nord"},
        {"key": "adjacent_south", "label": "Limita sud"},
        {"key": "adjacent_east", "label": "Limita est"},
        {"key": "adjacent_west", "label": "Limita oest"},
    ],
    "Edificacio": [
        {"key": "building_type", "label": "Tipus edifici"},
        {"key": "num_floors", "label": "Plantes"},
        {"key": "superficie_construida", "label": "Sup. construida"},
        {"key": "superficie_parcela", "label": "Sup. parcela"},
        {"key": "cota_referencia", "label": "Cota referencia"},
        {"key": "site_condition", "label": "Estat terreny"},
        {"key": "site_description", "label": "Descripcio solar"},
        {"key": "access_description", "label": "Acces"},
    ],
    "Camp DPSH": [
        {"key": "num_dpsh_tests", "label": "Num. assaigs DPSH", "check": "truthy_nonzero"},
        {"key": "dpsh_test_ids", "label": "IDs assaigs"},
        {"key": "dpsh_avg_n20", "label": "N20 mitja"},
        {"key": "dpsh_tests", "label": "Taula DPSH", "check": "array_filled"},
    ],
    "Camp Sondeig": [
        {"key": "sondeig_tests", "label": "Taula sondeig", "check": "array_filled",
         "conditional": "has_sondeig"},
    ],
    "Camp Lab": [
        {"key": "sulfate_value", "label": "Sulfats (mg/kg)"},
    ],
    "Geologia": [
        {"key": "geology_paragraphs", "label": "Paragrafs geologia", "check": "array_filled"},
        {"key": "radon_zone", "label": "Zona rado"},
        {"key": "seismic_ab_text", "label": "Coeficient sismic ab"},
        {"key": "materials_level_1", "label": "Materials nivell 1"},
    ],
    "Geotecnia": [
        {"key": "geotech_density", "label": "Densitat gamma"},
        {"key": "geotech_cohesion", "label": "Cohesio c"},
        {"key": "geotech_phi", "label": "Angle friccio phi"},
        {"key": "geotech_E", "label": "Modul deformacio E"},
        {"key": "geotech_nb", "label": "Nb"},
        {"key": "soil_level_rows", "label": "Taula nivells sol", "check": "array_filled"},
        {"key": "perm_rows", "label": "Taula permeabilitat", "check": "array_filled"},
    ],
    "Calculs": [
        {"key": "qa_value", "label": "Qa capacitat portant"},
        {"key": "settlement", "label": "Assentament"},
        {"key": "k30_value", "label": "Coef. balast K30"},
    ],
}


def _is_filled(value: Any, check: str = "truthy") -> bool:
    """Check if a template context value is meaningfully filled."""
    if check == "truthy_nonzero":
        return value is not None and value != '' and value != 0 and value != '0'
    if check == "array_filled":
        if not isinstance(value, list) or len(value) == 0:
            return False
        # Check first element has at least one non-empty value
        first = value[0]
        if isinstance(first, dict):
            return any(bool(v) for v in first.values())
        return bool(first)
    # Default: truthy
    return bool(value)


@router.get("/report-readiness/{project_name:path}")
def report_readiness(project_name: str):
    """Run full report pipeline (minus rendering) and return variable fill status."""
    import time
    t0 = time.monotonic()

    try:
        project_path = wizard_service._resolve_project(project_name)

        # Merge current prefills into user_data so the readiness check
        # reflects what SmartScan/auto_extract found (not just saved data).
        prefills = wizard_service.get_prefills(project_name)
        user_data_path = project_path / 'user_data.json'
        merged_ud: dict[str, Any] = {}
        if user_data_path.exists():
            import json as _json
            try:
                merged_ud = _json.loads(user_data_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        # Flatten prefills {key: {value, source}} -> {key: value}
        for k, v in prefills.items():
            if k.startswith('_'):
                continue
            val = v.get('value') if isinstance(v, dict) else v
            if val and k not in merged_ud:
                merged_ud[k] = val

        from automation.report_generator import ReportGenerator
        generator = ReportGenerator(project_path=str(project_path), user_data=merged_ud)
        result = generator.build_context_preview()

        ctx = result.context
        categories = []
        total_filled = 0
        total_count = 0

        for cat_name, var_defs in READINESS_VARIABLES.items():
            cat_vars = []
            cat_filled = 0
            cat_total = 0

            for vdef in var_defs:
                key = vdef["key"]
                # Skip conditional variables when condition is false
                cond = vdef.get("conditional")
                if cond and not ctx.get(cond):
                    continue

                check = vdef.get("check", "truthy")
                value = ctx.get(key)
                filled = _is_filled(value, check)
                cat_total += 1
                if filled:
                    cat_filled += 1

                # Truncate display value
                display = ""
                if value is not None:
                    if isinstance(value, list):
                        display = f"[{len(value)} items]"
                    else:
                        display = str(value)[:120]

                cat_vars.append({
                    "key": key,
                    "label": vdef["label"],
                    "filled": filled,
                    "value": display,
                })

            total_filled += cat_filled
            total_count += cat_total
            categories.append({
                "name": cat_name,
                "filled": cat_filled,
                "total": cat_total,
                "pct": round(cat_filled / cat_total * 100, 1) if cat_total else 0,
                "variables": cat_vars,
            })

        elapsed_ms = round((time.monotonic() - t0) * 1000)

        return {
            "overall": {
                "filled": total_filled,
                "total": total_count,
                "pct": round(total_filled / total_count * 100, 1) if total_count else 0,
            },
            "categories": categories,
            "errors": result.errors,
            "warnings": result.warnings,
            "elapsed_ms": elapsed_ms,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error in report readiness for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


# --- Groq Vision endpoints ---

@router.post("/vision-groq/{project_name:path}")
def start_vision_groq_endpoint(project_name: str, req: VisionStartRequest | None = None):
    """Start Groq vision extraction (Llama 4 Scout, parallel, ~5s)."""
    force = req.force if req else False

    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not set")

    try:
        project_path = wizard_service._resolve_project(project_name)
        from . import vision_groq
        result = vision_groq.start_vision_groq(project_name, project_path, force=force)
        status_code = 202 if result["status"] == "started" else 200
        return JSONResponse(content=result, status_code=status_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error starting Groq vision for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vision-claude/{project_name:path}")
def start_vision_claude_endpoint(project_name: str, req: VisionStartRequest | None = None):
    """Start Claude vision extraction (Sonnet, better for small text, ~27x more expensive)."""
    force = req.force if req else False

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not set")

    try:
        project_path = wizard_service._resolve_project(project_name)
        from .vision_groq import run_vision_groq_sync
        result = run_vision_groq_sync(project_path, force_refresh=force, vision_backend="claude")
        return {"status": "done", "results": {k: v for k, v in result.items()}}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error starting Claude vision for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vision-groq-status/{project_name:path}")
def vision_groq_status(project_name: str):
    """Check Groq vision extraction status."""
    try:
        from . import vision_groq
        status = vision_groq.get_groq_vision_status(project_name)
        file_status = wizard_service.get_vision_status(project_name)
        return {**status, "files": file_status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/groq-cache")
def clear_groq_cache():
    """Clear the Groq extraction cache."""
    import shutil
    cache_dir = config.cache_dir("groq")
    count = 0
    if cache_dir.exists():
        count = len(list(cache_dir.glob("*.json")))
        shutil.rmtree(cache_dir)
    return {"cleared": count, "message": f"Cleared {count} cached extractions"}


# --- Human-in-the-loop: targeted evidence upload + extraction ---

_UPLOAD_EXT_ALLOWLIST: frozenset[str] = frozenset({
    '.pdf', '.xls', '.xlsx', '.docx', '.doc', '.msg', '.txt',
    '.jpg', '.jpeg', '.png',
})
_UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024  # 25 MB


def _safe_upload_filename(raw_name: str) -> str:
    """Sanitize an uploaded filename: strip path separators, NFKD-normalize,
    keep only a conservative set of characters. Never returns an empty string."""
    import re
    import unicodedata

    base = Path(raw_name).name  # strip any directory parts
    # NFKD normalize then drop non-ASCII; if that nukes everything, fall back.
    norm = unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode('ascii')
    # Allow letters, digits, dot, dash, underscore; collapse everything else to '_'.
    clean = re.sub(r'[^A-Za-z0-9._-]+', '_', norm).strip('._-')
    return clean or 'upload'


@router.post("/upload-evidence/{project_name:path}")
async def upload_evidence(project_name: str, file: UploadFile = File(...)):
    """Accept a file Eva uploads as evidence for missing wizard fields.

    Stores under `{project}/validation/uploads/<YYYYMMDD-HHMMSS>_<rand>_<safe>`.
    Returns an `upload_id` the frontend passes to `/extract-targeted`.
    """
    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    raw_name = file.filename or 'upload'
    suffix = Path(raw_name).suffix.lower()
    if suffix not in _UPLOAD_EXT_ALLOWLIST:
        raise HTTPException(
            status_code=415,
            detail=f"Extensió no permesa: {suffix or '(cap)'}. "
                   f"Acceptades: {sorted(_UPLOAD_EXT_ALLOWLIST)}",
        )

    # Stream-read with a size cap to avoid buffering untrusted data in memory.
    import datetime
    import secrets
    data = await file.read(_UPLOAD_MAX_BYTES + 1)
    if len(data) > _UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fitxer massa gran ({len(data) / 1024 / 1024:.1f} MB). "
                   f"Màxim: {_UPLOAD_MAX_BYTES / 1024 / 1024:.0f} MB.",
        )

    uploads_dir = project_path / 'validation' / 'uploads'
    uploads_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    rand = secrets.token_hex(3)
    safe = _safe_upload_filename(raw_name)
    upload_id = f"{ts}_{rand}_{safe}"
    stored_path = uploads_dir / upload_id

    stored_path.write_bytes(data)

    rel_path = stored_path.relative_to(project_path).as_posix()
    logger.info("evidence upload: %s -> %s (%d bytes)", project_name, rel_path, len(data))
    return {
        "upload_id": upload_id,
        "stored_path": rel_path,
        "size_bytes": len(data),
        "mime": file.content_type or 'application/octet-stream',
    }


@router.post("/extract-targeted/{project_name:path}")
def extract_targeted_endpoint(project_name: str, body: TargetedExtractRequest):
    """Run the hybrid targeted extractor (regex → cc_extractor) on one file.

    The file is identified by either `upload_id` (previously posted to
    /upload-evidence) or `file_path` (relative path inside the project folder;
    path traversal rejected). Returns extracted values with confidence; does
    NOT persist — the frontend must POST to /wizard/{project} to save.
    """
    from web.expected_sources import CONFIDENCE_THRESHOLD

    try:
        project_path = wizard_service._resolve_project(project_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not body.concept_ids:
        raise HTTPException(status_code=400, detail="concept_ids must not be empty")
    if not body.upload_id and not body.file_path:
        raise HTTPException(status_code=400, detail="Provide either upload_id or file_path")

    # Resolve target file, reject path traversal.
    if body.upload_id:
        candidate = project_path / 'validation' / 'uploads' / body.upload_id
    else:
        candidate = project_path / body.file_path  # type: ignore[arg-type]

    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="file not found")

    try:
        resolved.relative_to(project_path.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="file must live inside the project directory")

    import time
    from automation.targeted_extraction import extract_targeted

    t0 = time.monotonic()
    results = extract_targeted(resolved, body.concept_ids, project_path)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Annotate low-confidence entries for the UI confirmation step.
    for cid, entry in results.items():
        conf = entry.get("confidence")
        value = entry.get("value")
        entry["needs_confirmation"] = bool(
            value not in (None, "") and (conf is None or conf < CONFIDENCE_THRESHOLD)
        )

    return {
        "source_file": resolved.relative_to(project_path.resolve()).as_posix(),
        "results": results,
        "elapsed_ms": elapsed_ms,
    }
