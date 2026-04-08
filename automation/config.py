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
    # Functions
    "has_provider",
    "available_vision_backends",
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
G3DT_PROJECTS_DIR: str = _env(
    "G3DT_PROJECTS_DIR", str(_PROJECT_ROOT / "reference-material")
)


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
