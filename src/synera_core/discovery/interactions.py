"""Core multi-stressor interaction discovery engine.

Detects synergisms, antagonisms, and nonlinear interaction effects between pairs
and sets of environmental stressors against response outcomes.
"""

from __future__ import annotations

from enum import Enum


class InteractionType(str, Enum):
    """Classification of multi-stressor interaction effects."""

    SYNERGISTIC = "SYNERGISTIC"      # Combined > additive expectation
    ANTAGONISTIC = "ANTAGONISTIC"    # Combined < additive expectation
    NONLINEAR = "NONLINEAR"          # Threshold / non-monotonic response
    ADDITIVE = "ADDITIVE"            # Multiplicative independence on fold-change scale


def compute_additive_expectation(
    effect_a: float,
    effect_b: float,
) -> float:
    """Compute additive expectation on log2-scale.

    Note: On log2-fold-change scale, additivity represents multiplicative independence
    on the linear fold-change scale.
    """
    return effect_a + effect_b
