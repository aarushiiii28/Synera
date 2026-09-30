"""Cross-dataset replication and generalizability validation."""

from __future__ import annotations

from typing import Dict, Any


def evaluate_replication(
    primary_effect: float,
    replication_effect: float,
    primary_p: float,
    replication_p: float,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Test concordance and directional consistency across independent datasets.

    Args:
        primary_effect: Effect size in discovery dataset.
        replication_effect: Effect size in holdout/replication dataset.
        primary_p: P-value in discovery dataset.
        replication_p: P-value in replication dataset.
        alpha: Nominal significance threshold.

    Returns:
        Dictionary reporting replication status, directional consistency, and summary.
    """
    same_sign = (primary_effect * replication_effect) > 0
    replicated = same_sign and (replication_p < alpha) and (primary_p < alpha)
    return {
        "replicated": replicated,
        "concordant_direction": same_sign,
        "primary_effect": primary_effect,
        "replication_effect": replication_effect,
        "replication_p": replication_p,
    }
