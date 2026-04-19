"""LLM cost estimation -- single source of truth for Anthropic + Groq + OpenAI pricing.

Used by the diagnostic snapshot to compute per-project USD spend across
providers (Anthropic via direct API or OpenRouter; Groq via direct API;
OpenAI via direct API).

Anthropic pricing sourced from anthropic.com/pricing observed 2026-04-18.
OpenAI pricing sourced from openai.com/api/pricing observed 2026-04-18.
Groq pricing is re-exported from
``automation.fileminer.miners.groq_miner.GROQ_PRICING`` (single table).
"""
from __future__ import annotations

import logging

from automation.fileminer.miners.groq_miner import GROQ_PRICING

logger = logging.getLogger(__name__)

__all__ = ["ANTHROPIC_PRICING", "GROQ_PRICING", "OPENAI_PRICING", "estimate_cost"]

# $/Mtok (input, output) -- anthropic.com/pricing 2026-04-18.
ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# $/Mtok (input, output) -- openai.com/api/pricing 2026-04-18.
OPENAI_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


def estimate_cost(provider: str, model: str, in_tok: int, out_tok: int) -> float:
    """Return estimated USD cost for a token usage pair.

    Args:
        provider: One of {"anthropic", "openrouter", "groq", "openai"}.
        model: Model identifier. For "openrouter", the leading "anthropic/"
            prefix is stripped before lookup against ANTHROPIC_PRICING.
        in_tok: Input tokens consumed.
        out_tok: Output tokens consumed.

    Returns:
        Estimated cost in USD. Unknown model/provider returns 0.0 with a
        warning log -- never raises.
    """
    p = (provider or "").strip().lower()
    m = model or ""

    if p == "groq":
        prices = GROQ_PRICING.get(m)
    elif p == "anthropic":
        prices = ANTHROPIC_PRICING.get(m)
    elif p == "openai":
        prices = OPENAI_PRICING.get(m)
    elif p == "openrouter":
        slug = m.split("anthropic/", 1)[1] if m.startswith("anthropic/") else m
        prices = ANTHROPIC_PRICING.get(slug)
    else:
        logger.warning("estimate_cost: unknown provider %r", provider)
        return 0.0

    if prices is None:
        logger.warning("estimate_cost: unknown model %r for provider %r", model, provider)
        return 0.0

    in_price, out_price = prices
    return (in_tok * in_price + out_tok * out_price) / 1_000_000
