"""
FastAPI router with all API endpoints for the G3DT web wizard.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import wizard_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# --- Request/response models ---

class WizardSaveRequest(BaseModel):
    wizard_fields: dict[str, Any]
    expert_overrides: dict[str, Any] | None = None


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


@router.get("/prefills/{project_name:path}")
def get_prefills(project_name: str, refresh: bool = False):
    """Get auto-extracted + wizard prefills for a project."""
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
def prefills_stream(project_name: str):
    """SSE endpoint: streams progress events during extraction, then final prefills."""
    try:
        wizard_service._resolve_project(project_name)  # Validate project exists
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return StreamingResponse(
        wizard_service.get_prefills_streaming(project_name),
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
    """Start Claude CLI vision extraction for a project (non-blocking)."""
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


@router.post("/wizard/{project_name:path}")
def save_wizard(project_name: str, req: WizardSaveRequest):
    """Save wizard data to user_data.json."""
    try:
        path = wizard_service.save_wizard(
            project_name, req.wizard_fields, req.expert_overrides
        )
        return {"saved": True, "path": str(path)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error saving wizard for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/{project_name:path}", response_model=GenerateResponse)
def generate_report(project_name: str):
    """Generate the geotechnical report .docx."""
    try:
        result = wizard_service.generate_report(project_name)
        return GenerateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error generating report for %s", project_name)
        raise HTTPException(status_code=500, detail=str(e))


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
