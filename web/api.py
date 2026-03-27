"""
FastAPI router with all API endpoints for the G3DT web wizard.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import wizard_service
from . import vision_fast

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
    model: str = "qwen/qwen3-32b"
    clear_cache: bool = False


@router.post("/groq-mine/{project_name:path}")
def groq_mine(project_name: str, req: GroqMineRequest | None = None):
    """Run Groq deep mine on a project with specified model."""
    import shutil

    model = req.model if req else "qwen/qwen3-32b"
    clear_cache = req.clear_cache if req else False

    os.environ["G3DT_USE_GROQ"] = "1"
    os.environ["GROQ_MODEL"] = model

    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not set")

    if clear_cache:
        cache_dir = Path.home() / ".g3dt" / "cache" / "groq"
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
                "id": "meta-llama/llama-4-scout-17b-16e-instruct",
                "name": "Llama 4 Scout 17Bx16E",
                "input_price_per_m": 0.11,
                "output_price_per_m": 0.34,
                "speed_tps": 594,
                "context_window": 131072,
                "notes": "MoE architecture. Good quality/price ratio.",
            },
        ],
        "current_model": os.environ.get("GROQ_MODEL", "qwen/qwen3-32b"),
        "api_key_set": bool(os.environ.get("GROQ_API_KEY")),
    }


class SetModelRequest(BaseModel):
    model: str


@router.post("/groq-model")
def set_groq_model(req: SetModelRequest):
    """Set the Groq text miner model at runtime."""
    valid_models = {
        "llama-3.1-8b-instant", "qwen/qwen3-32b",
        "llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct",
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
        {"key": "spt_test_id", "label": "SPT test ID", "conditional": "has_sondeig"},
    ],
    "Camp Lab": [
        {"key": "sulfate_value", "label": "Sulfats (mg/kg)"},
        {"key": "lab_sample_id", "label": "ID mostra lab"},
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

        from automation.report_generator import ReportGenerator
        generator = ReportGenerator(project_path=str(project_path))
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
    cache_dir = Path.home() / ".g3dt" / "cache" / "groq"
    count = 0
    if cache_dir.exists():
        count = len(list(cache_dir.glob("*.json")))
        shutil.rmtree(cache_dir)
    return {"cleared": count, "message": f"Cleared {count} cached extractions"}
