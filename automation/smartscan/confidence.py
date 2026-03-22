"""
SmartScan confidence scoring utilities.

Centralizes confidence thresholds and scoring logic across tiers.
"""

from __future__ import annotations


# Confidence thresholds
THRESHOLD_CLASSIFIED = 0.6    # Above this → classified with role
THRESHOLD_SUGGESTION = 0.3    # 0.3-0.6 → suggestion (Eva confirms)
# Below 0.3 → unknown

# Tier-specific base confidences
TIER1_BASE_HIGH = 0.95        # Exact regex match
TIER1_BASE_MEDIUM = 0.85      # Looser regex match
TIER2_BASE = 0.75             # Good fingerprint match
TIER2_KEYWORD_BOOST = 0.05    # Per matching keyword (max 3 boosts)
TIER3_BASE = 0.80             # Claude vision classification


def tier1_confidence(exact_match: bool = True) -> float:
    """Confidence for Tier 1 (filename pattern) matches."""
    return TIER1_BASE_HIGH if exact_match else TIER1_BASE_MEDIUM


def tier2_confidence(
    keyword_hits: int = 0,
    structural_match: bool = False,
    metadata_match: bool = False,
) -> float:
    """
    Confidence for Tier 2 (fingerprint) matches.

    Args:
        keyword_hits: Number of role-specific keywords found in text
        structural_match: Page dimensions/ratio match expected profile
        metadata_match: PDF producer/creator matches expected source
    """
    score = TIER2_BASE
    score += min(keyword_hits, 3) * TIER2_KEYWORD_BOOST
    if structural_match:
        score += 0.05
    if metadata_match:
        score += 0.05
    return min(score, 0.95)


def classify_category(confidence: float, role: str | None) -> str:
    """Determine classification category from confidence and role."""
    if role is None:
        return "unknown"
    if confidence >= THRESHOLD_CLASSIFIED:
        return "classified"
    if confidence >= THRESHOLD_SUGGESTION:
        return "suggestion"
    return "unknown"
