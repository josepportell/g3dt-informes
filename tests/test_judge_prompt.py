"""Hermetic tests for the LLM judge system prompt.

These tests verify the prompt text contains the cross-language tolerance
clauses, preposition-variant clauses, strict-measurements section, and
worked examples added in fix/judge-cross-language-tolerance.

No LLM calls. Pure string-containment checks against the exported prompt.
"""

from __future__ import annotations

from scripts.compare_benchmarks import get_judge_system_prompt


def test_prompt_has_cross_language_clause() -> None:
    prompt = get_judge_system_prompt()
    assert "Cross-language equivalence" in prompt, (
        "Prompt must explicitly cover Catalan<->Spanish cross-language equivalence."
    )


def test_prompt_has_preposition_variant_clause() -> None:
    prompt = get_judge_system_prompt()
    assert "Preposition variants" in prompt, (
        "Prompt must explicitly cover preposition variants in place names."
    )
    assert "Vilanova de Segrià" in prompt, (
        "Prompt must include the Vilanova de Segrià preposition example."
    )


def test_prompt_has_strict_measurements_section() -> None:
    prompt = get_judge_system_prompt()
    assert "## Strict on measurements" in prompt, (
        "Prompt must include a dedicated '## Strict on measurements' section."
    )


def test_prompt_has_cross_language_worked_example() -> None:
    prompt = get_judge_system_prompt()
    assert "Per la part nord" in prompt, (
        "Prompt must include the Catalan half of the cross-language worked example."
    )
    assert "Por la parte norte" in prompt, (
        "Prompt must include the Spanish half of the cross-language worked example."
    )
