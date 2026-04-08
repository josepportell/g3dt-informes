"""
G3DT Web Server — FastAPI app serving the wizard UI + API.

Run:
    uv run python -m web.server
    # or
    uv run uvicorn web.server:app --port 8765 --reload
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from automation.log_setup import setup_logging
from .api import router

setup_logging()

app = FastAPI(title="G3DT Web Wizard", version="0.7.0")

# API routes
app.include_router(router)

# Static files (serves review.html at /)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "templates" / "validation"
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")


def main():
    import uvicorn
    print("G3DT Web Wizard: http://localhost:8765")
    print("  review.html → http://localhost:8765/review.html")
    uvicorn.run(app, host="0.0.0.0", port=8765)


if __name__ == "__main__":
    main()
