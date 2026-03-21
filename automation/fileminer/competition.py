"""
Signal competition: when multiple signals target the same variable, pick the winner.

Default: deterministic resolution by priority (lower wins), then confidence (higher wins).
Designed to be replaceable with an LLM-based resolver in Phase G.
"""

from __future__ import annotations

from .models import Signal, ResolvedValue


def resolve_competition(
    signals: list[Signal],
) -> dict[str, ResolvedValue]:
    """Resolve competing signals into one winner per report variable.

    Groups signals by maps_to, then for each variable picks the best signal.
    Signals with maps_to=None are skipped (unmapped data).

    Args:
        signals: All signals from all miners

    Returns:
        Dict of variable_name -> ResolvedValue (winner + alternatives)
    """
    grouped: dict[str, list[Signal]] = {}
    for s in signals:
        if s.maps_to is not None:
            grouped.setdefault(s.maps_to, []).append(s)

    resolved: dict[str, ResolvedValue] = {}
    for variable, candidates in grouped.items():
        ranked = sorted(candidates, key=lambda s: (s.priority, -s.confidence))
        winner = ranked[0]
        alternatives = ranked[1:]
        resolved[variable] = ResolvedValue(
            variable=variable,
            value=winner.value,
            source=winner.source_file,
            confidence=winner.confidence,
            signal=winner,
            alternatives=alternatives,
        )

    return resolved
