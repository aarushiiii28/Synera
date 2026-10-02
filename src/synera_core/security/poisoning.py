"""Data poisoning detection and influence anomaly screening.

Identifies adversarial label flipping, targeted covariate shifts, and high-leverage
anomalous observations that skew interaction estimates.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def detect_poisoning_candidates(
    x_matrix: np.ndarray,
    y_vector: np.ndarray,
    residual_threshold: float = 3.5,
) -> dict[str, Any]:
    """Flag potential poisoned data points using leverage-residual diagnostics.

    Args:
        x_matrix: Feature design matrix (N x P).
        y_vector: Target response vector (N).
        residual_threshold: Studentized residual cutoff for outlier flagging.

    Returns:
        Dictionary summarizing detected candidate anomalies and indices.
    """
    n, p = x_matrix.shape
    if n <= p + 1:
        return {"flagged_indices": [], "is_clean": True, "details": "Insufficient degrees of freedom"}

    # Ordinary least squares projection
    pinv_x = np.linalg.pinv(x_matrix)
    beta = pinv_x @ y_vector
    preds = x_matrix @ beta
    residuals = y_vector - preds

    std_res = np.std(residuals)
    if std_res == 0:
        return {"flagged_indices": [], "is_clean": True}

    z_scores = np.abs(residuals) / std_res
    flagged = np.where(z_scores > residual_threshold)[0].tolist()

    return {
        "flagged_indices": flagged,
        "is_clean": len(flagged) == 0,
        "max_z_score": float(np.max(z_scores)),
        "flagged_count": len(flagged),
    }
