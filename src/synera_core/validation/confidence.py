"""Composite confidence score indicator calculation.

Combines statistical significance, cross-dataset replication, empirical robustness,
and cryptographic provenance trust into an aggregate indicator score in [0, 1].
"""

from __future__ import annotations

from synera_core.config import ConfidenceWeightsConfig


def calculate_confidence_score(
    stat_score: float,
    replication_score: float,
    robustness_score: float,
    trust_score: float,
    weights: ConfidenceWeightsConfig | None = None,
) -> float:
    """Calculate composite confidence indicator.

    Args:
        stat_score: Statistical validity score [0, 1].
        replication_score: Cross-dataset replication score [0, 1].
        robustness_score: Resampling/bootstrap stability score [0, 1].
        trust_score: Cryptographic integrity and provenance score [0, 1].
        weights: Optional custom weight configuration.

    Returns:
        Weighted confidence score bounded between 0.0 and 1.0.
    """
    if weights is None:
        weights = ConfidenceWeightsConfig()

    composite = (
        weights.stat * max(0.0, min(1.0, stat_score))
        + weights.replication * max(0.0, min(1.0, replication_score))
        + weights.robustness * max(0.0, min(1.0, robustness_score))
        + weights.trust * max(0.0, min(1.0, trust_score))
    )
    return round(float(composite), 4)
