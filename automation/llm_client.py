"""LLM client factory — pluggable provider for Anthropic-format calls.

Supports:
  - Anthropic direct (default): api.anthropic.com
  - OpenRouter (Anthropic-format): openrouter.ai/api/v1 — mirrors /v1/messages,
    so the official `anthropic` Python SDK works with only a `base_url` override.

Configured via env vars:
  G3DT_LLM_PROVIDER   "anthropic" (default) | "openrouter"
  ANTHROPIC_API_KEY   required for anthropic provider (read by SDK directly)
  OPENROUTER_API_KEY  required for openrouter provider
  G3DT_CC_MODEL       model id for cc_extractor vision/text calls
  G3DT_JUDGE_MODEL    model id for compare_results LLM judge (Haiku-class)

Model IDs differ by provider:
  Anthropic direct:  e.g. "claude-sonnet-4-5-20250929", "claude-opus-4-7"
  OpenRouter:        e.g. "anthropic/claude-sonnet-4.5", "anthropic/claude-opus-4.7"

If G3DT_CC_MODEL / G3DT_JUDGE_MODEL are unset we pick a sane default per provider.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_DEFAULT_CC_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openrouter": "anthropic/claude-sonnet-4.6",
}

_DEFAULT_JUDGE_MODELS = {
    # Single-user app; no volume to justify a cheaper judge. Keep Sonnet 4.6
    # across the stack so comparison quality matches extraction quality.
    "anthropic": "claude-sonnet-4-6",
    "openrouter": "anthropic/claude-sonnet-4.6",
}


def _load_dotenv_if_present() -> None:
    """Populate os.environ from project-root .env file if any key is unset.

    Does not override pre-existing env vars. Zero-dependency parser (no
    python-dotenv requirement).
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Load .env once at module import so downstream callers can read env vars
# without needing the user to manually source the file.
_load_dotenv_if_present()


def active_provider() -> str:
    """Return the current provider name ("anthropic" or "openrouter")."""
    return (os.environ.get("G3DT_LLM_PROVIDER") or "anthropic").lower()


def get_anthropic_client() -> Any:
    """Return an `anthropic.Anthropic` client configured for the active provider."""
    import anthropic

    provider = active_provider()
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "G3DT_LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set"
            )
        # Anthropic SDK appends `/v1/messages`, so base_url stops at `/api`.
        return anthropic.Anthropic(
            base_url="https://openrouter.ai/api",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://eficients.cat",
                "X-Title": "G3DT",
            },
        )
    # Anthropic direct — SDK reads ANTHROPIC_API_KEY from env by default.
    return anthropic.Anthropic()


def get_cc_model() -> str:
    """Model id for CC-Agentic vision/text extraction."""
    explicit = os.environ.get("G3DT_CC_MODEL")
    if explicit:
        return explicit
    return _DEFAULT_CC_MODELS[active_provider()]


def get_judge_model() -> str:
    """Model id for compare_results LLM judge (cheap Haiku-class)."""
    explicit = os.environ.get("G3DT_JUDGE_MODEL")
    if explicit:
        return explicit
    return _DEFAULT_JUDGE_MODELS[active_provider()]
