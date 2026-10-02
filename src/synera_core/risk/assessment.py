"""Layer 07 Action: Environmental risk assessment and decision support."""

from __future__ import annotations


def calculate_synergistic_risk_multiplier(
    marginal_risk_a: float,
    marginal_risk_b: float,
    interaction_effect: float,
) -> float:
    """Calculate compound risk index incorporating synergistic amplification.

    Args:
        marginal_risk_a: Baseline independent risk score of stressor A [0, 1].
        marginal_risk_b: Baseline independent risk score of stressor B [0, 1].
        interaction_effect: Validated interaction effect size.

    Returns:
        Risk multiplier score.
    """
    additive_baseline = marginal_risk_a + marginal_risk_b
    if interaction_effect > 0:
        amplification = 1.0 + interaction_effect
        return round(additive_baseline * amplification, 4)
    # Antagonistic damping
    damping = max(0.2, 1.0 + interaction_effect)
    return round(additive_baseline * damping, 4)
