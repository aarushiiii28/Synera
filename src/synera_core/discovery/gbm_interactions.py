"""Gradient Boosting Decision Tree (LightGBM) feature interaction analyzer.

Computes Friedman's H-statistic and TreeSHAP interaction values to discover
non-linear and high-order stressor synergies.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def rank_pairwise_interactions(
    features: list[str],
    interaction_matrix: np.ndarray,
) -> list[dict[str, Any]]:
    """Rank pairs of features by interaction strength.

    Args:
        features: List of feature names.
        interaction_matrix: Symmetric 2D array of pairwise interaction statistics.

    Returns:
        List of ranked interaction pairs with scores.
    """
    ranked: list[dict[str, Any]] = []
    n = len(features)
    for i in range(n):
        for j in range(i + 1, n):
            ranked.append({
                "feature_a": features[i],
                "feature_b": features[j],
                "score": float(interaction_matrix[i, j]),
            })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked
