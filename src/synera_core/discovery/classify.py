"""Classification and categorization of discovered interaction types."""

from __future__ import annotations

from synera_core.discovery.interactions import InteractionType


def classify_interaction_effect(
    observed_effect: float,
    additive_expectation: float,
    p_value: float,
    alpha: float = 0.05,
    min_abs_effect: float = 0.5,
) -> InteractionType:
    """Classify the nature of an interaction given statistical test outcomes.

    Args:
        observed_effect: Observed joint response on log2 scale.
        additive_expectation: Sum of marginal effects on log2 scale.
        p_value: Multiple-testing corrected p-value for interaction term.
        alpha: Significance threshold.
        min_abs_effect: Minimum absolute effect size difference.

    Returns:
        InteractionType enum value.
    """
    if p_value >= alpha:
        return InteractionType.ADDITIVE

    diff = observed_effect - additive_expectation
    if abs(diff) < min_abs_effect:
        return InteractionType.ADDITIVE

    if diff > 0:
        return InteractionType.SYNERGISTIC
    return InteractionType.ANTAGONISTIC
