"""
G3DT Central Configuration

Loads .env once at import time, exposes all settings as module-level constants.

Usage:
    from automation import config
    print(config.VISION_MODEL_OPENAI)
    if config.has_provider("groq"):
        ...
"""
from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    # Paths
    "PROJECT_ROOT",
    # API keys
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    # Vision models
    "VISION_MODEL_OPENAI",
    "VISION_MODEL_ANTHROPIC",
    "VISION_MODEL_GROQ",
    # Text models
    "TEXT_MODEL_GROQ",
    "TEXT_MODEL_ANTHROPIC",
    # Fallback orders
    "VISION_FALLBACK_ORDER",
    "PROBE_FALLBACK_ORDER",
    "VISION_BACKEND_BY_TYPE",
    # Logging
    "LOG_ENABLED",
    "LOG_PATH",
    "LOG_LEVEL",
    "LOG_DEPTH",
    # Feature flags
    "G3DT_USE_SMARTSCAN",
    "G3DT_USE_GROQ",
    "G3DT_NO_CACHE",
    "G3DT_PROJECTS_DIR",
    "G3DT_ENABLE_AI_PIPELINE",
    "G3DT_DEV_MODE",
    "G3DT_PROD_USE_CLAUDECODE_VISION",
    # Production paths (workflow xarxa + workspace local + copy-back)
    "G3DT_NETWORK_PROJECTS",
    "G3DT_LOCAL_WORKSPACE",
    "G3DT_REPORTS_DIR",
    "G3DT_CACHE_DIR",
    # Tier 3 vision
    "MAX_PAGES_TIER3",
    # Functions
    "has_provider",
    "available_vision_backends",
    "cache_dir",
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Read .env from project root into os.environ (setdefault, won't override)."""
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


def _env_list(key: str, default: list[str] | None = None) -> list[str]:
    val = os.environ.get(key)
    if val is None:
        return default if default is not None else []
    return [item.strip() for item in val.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = _PROJECT_ROOT

# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY: str = _env("ANTHROPIC_API_KEY")
OPENAI_API_KEY: str = _env("OPENAI_API_KEY")
GROQ_API_KEY: str = _env("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# Vision models
# ---------------------------------------------------------------------------

VISION_MODEL_OPENAI: str = _env("OPENAI_VISION_MODEL", "gpt-4.1-mini")
VISION_MODEL_ANTHROPIC: str = _env("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")
VISION_MODEL_GROQ: str = _env("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# ---------------------------------------------------------------------------
# Text models
# ---------------------------------------------------------------------------

TEXT_MODEL_GROQ: str = _env("GROQ_TEXT_MODEL", "qwen/qwen3-32b")
TEXT_MODEL_ANTHROPIC: str = _env("ANTHROPIC_TEXT_MODEL", "claude-sonnet-4-6")

# ---------------------------------------------------------------------------
# Fallback orders
# ---------------------------------------------------------------------------

VISION_FALLBACK_ORDER: list[str] = _env_list(
    "VISION_FALLBACK", ["openai", "anthropic", "groq"]
)
PROBE_FALLBACK_ORDER: list[str] = _env_list(
    "PROBE_FALLBACK", ["groq", "openai", "anthropic"]
)

# Per-vision-type backend override. None = use the run's default vision_backend.
# Handwritten field sheets need Claude precision (sondeig depth columns,
# DPSH handwritten N20). Printed PDFs (planol, projecte) work fine on OpenAI.
VISION_BACKEND_BY_TYPE: dict[str, str] = {
    "sondeig":             os.environ.get("G3DT_VISION_BACKEND_SONDEIG",  "anthropic"),
    "sondeig_annex":       os.environ.get("G3DT_VISION_BACKEND_SONDEIG_ANNEX", "anthropic"),
    "dpsh":                os.environ.get("G3DT_VISION_BACKEND_DPSH",     "anthropic"),
    "planol":              os.environ.get("G3DT_VISION_BACKEND_PLANOL",   "openai"),
    "projecte_arquitecte": os.environ.get("G3DT_VISION_BACKEND_PROJECTE", "openai"),
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_ENABLED: bool = _env_bool("G3DT_LOG_ENABLED", True)
LOG_PATH: str | None = _env("G3DT_LOG_PATH") or None
LOG_LEVEL: str = _env("G3DT_LOG_LEVEL", "INFO")
LOG_DEPTH: str = _env("G3DT_LOG_DEPTH", "NORMAL")
LOG_ROTATE_DAILY: bool = _env_bool("G3DT_LOG_ROTATE_DAILY", True)
LOG_KEEP_DAYS: int = int(_env("G3DT_LOG_KEEP_DAYS", "30"))

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

G3DT_USE_SMARTSCAN: bool = _env_bool("G3DT_USE_SMARTSCAN", True)
G3DT_USE_GROQ: bool = _env_bool("G3DT_USE_GROQ", False)
G3DT_NO_CACHE: bool = _env_bool("G3DT_NO_CACHE", False)
# Production v1 (2026-05-04): workflow còpia local + copy-back.
# Si G3DT_NETWORK_PROJECTS està configurat, el wizard llista projectes des
# d'aquí (xarxa de G3DT, F:\projectes), copia el projecte a G3DT_LOCAL_WORKSPACE
# abans de fer res, i al final copia el .docx a la carpeta original.
# Si no està configurat, fallback legacy: tot dins G3DT_PROJECTS_DIR.
G3DT_NETWORK_PROJECTS: str = _env("G3DT_NETWORK_PROJECTS", "")
G3DT_LOCAL_WORKSPACE: str = _env("G3DT_LOCAL_WORKSPACE", "")
G3DT_REPORTS_DIR: str = _env("G3DT_REPORTS_DIR", "")

# Cache base — outputs de geocode, ICGC, Cadastre, ortho, mapillary, groq...
# Default històric: `~/.g3dt/cache/` (al perfil de l'usuari Windows). A producció
# preferim una carpeta neta dedicada (`C:\g3dt-ia\cache\`) — ajustable via
# `G3DT_CACHE_DIR`. Tot el codi consumidor passa per `config.cache_dir(subdir)`.
G3DT_CACHE_DIR: str = _env("G3DT_CACHE_DIR", "")


def cache_dir(*subpath: str) -> Path:
    """Return cache dir, joining optional subpath segments.

    Reads from `G3DT_CACHE_DIR` env var when set, falls back to
    `~/.g3dt/cache/` for backwards-compat with existing dev installs.
    Always returns a `Path`; caller is responsible for `mkdir(parents=True,
    exist_ok=True)` on the leaf dir.
    """
    base = Path(G3DT_CACHE_DIR) if G3DT_CACHE_DIR else (Path.home() / ".g3dt" / "cache")
    return base.joinpath(*subpath)

# G3DT_PROJECTS_DIR és el path on opera el pipeline. Default històric:
# `reference-material/` (mode dev). En producció v1 amb workflow network,
# apunta automàticament al G3DT_LOCAL_WORKSPACE perquè tot el codi avall
# (wizard_service._resolve_project, file_scanner, etc.) trobi els projectes
# al workspace local sense més canvis. Override explícit via env-var també
# té prioritat (per backwards-compat dev).
_explicit_projects_dir = _env("G3DT_PROJECTS_DIR", "")
if _explicit_projects_dir:
    G3DT_PROJECTS_DIR: str = _explicit_projects_dir
elif G3DT_LOCAL_WORKSPACE:
    G3DT_PROJECTS_DIR: str = G3DT_LOCAL_WORKSPACE
else:
    G3DT_PROJECTS_DIR: str = str(_PROJECT_ROOT / "reference-material")

# AI pipeline experimental (Stages 2-5, Pass A/B/C): NO activar a producció v1.
# Quan és False, els endpoints /api/ai-pipeline/* no es registren.
G3DT_ENABLE_AI_PIPELINE: bool = _env_bool("G3DT_ENABLE_AI_PIPELINE", False)

# DEV mode: activa eines de desenvolupament/diagnòstic al wizard.
G3DT_DEV_MODE: bool = _env_bool("G3DT_DEV_MODE", False)

# Vision via Claude Code subprocess: activar només si Claude Code està
# instal·lat a l'ordinador del usuari final. Independent de G3DT_DEV_MODE
# perquè volem poder activar-lo a producció sense passar a dev mode.
G3DT_PROD_USE_CLAUDECODE_VISION: bool = _env_bool("G3DT_PROD_USE_CLAUDECODE_VISION", False)

MAX_PAGES_TIER3: int = max(1, int(_env("G3DT_TIER3_MAX_PAGES", "10")))


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

_PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def has_provider(name: str) -> bool:
    """Return True if the named provider has an API key configured."""
    env_key = _PROVIDER_KEYS.get(name.lower())
    if env_key is None:
        return False
    return bool(os.environ.get(env_key))


def available_vision_backends(order: list[str] | None = None) -> list[str]:
    """Return providers from *order* that have an API key set."""
    if order is None:
        order = VISION_FALLBACK_ORDER
    return [p for p in order if has_provider(p)]
