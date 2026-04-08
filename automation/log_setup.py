"""
G3DT Structured Logging Setup

Configures root logger from config constants.
Provides structured loggers for vision and LLM calls.

Usage:
    from automation.log_setup import setup_logging, log_vision_call, log_llm_call
    setup_logging()
"""
from __future__ import annotations

import logging
import sys
from typing import Any

__all__ = [
    "setup_logging",
    "log_vision_call",
    "log_llm_call",
]

_FORMATS = {
    "MINIMAL": "%(levelname)s: %(message)s",
    "NORMAL": "%(asctime)s %(name)s %(levelname)s: %(message)s",
    "FULL": "%(asctime)s %(name)s:%(lineno)d %(levelname)s: %(message)s",
}

_vision_logger = logging.getLogger("g3dt.vision")
_llm_logger = logging.getLogger("g3dt.llm")


def setup_logging() -> None:
    """Configure root logger from config constants.

    Supports stdout handler and an optional file handler.
    Safe to call multiple times; clears existing handlers first.
    """
    from automation import config

    root = logging.getLogger()

    # Clear existing handlers to allow re-configuration
    root.handlers.clear()

    if not config.LOG_ENABLED:
        root.addHandler(logging.NullHandler())
        return

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    root.setLevel(level)

    fmt_str = _FORMATS.get(config.LOG_DEPTH.upper(), _FORMATS["NORMAL"])
    formatter = logging.Formatter(fmt_str)

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # Optional file handler
    if config.LOG_PATH:
        file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def log_vision_call(
    provider: str,
    model: str,
    file_name: str,
    vtype: str,
    success: bool,
    tokens_in: int = 0,
    tokens_out: int = 0,
    elapsed_ms: int = 0,
    cost_estimate: float = 0.0,
) -> None:
    """Log a structured vision API call."""
    status = "OK" if success else "FAIL"
    _vision_logger.info(
        "VISION %s provider=%s model=%s file=%s type=%s "
        "tokens_in=%d tokens_out=%d elapsed_ms=%d cost=%.4f",
        status,
        provider,
        model,
        file_name,
        vtype,
        tokens_in,
        tokens_out,
        elapsed_ms,
        cost_estimate,
    )


def log_llm_call(
    provider: str,
    model: str,
    purpose: str,
    success: bool,
    tokens_in: int = 0,
    tokens_out: int = 0,
    elapsed_ms: int = 0,
    cost_estimate: float = 0.0,
) -> None:
    """Log a structured text LLM call (Groq mining, LLM synthesis, etc.)."""
    status = "OK" if success else "FAIL"
    _llm_logger.info(
        "LLM %s provider=%s model=%s purpose=%s "
        "tokens_in=%d tokens_out=%d elapsed_ms=%d cost=%.4f",
        status,
        provider,
        model,
        purpose,
        tokens_in,
        tokens_out,
        elapsed_ms,
        cost_estimate,
    )
