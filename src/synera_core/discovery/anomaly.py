"""Multi-stressor compound anomaly detector.

Identifies multivariate environmental anomaly events where multiple stressors
co-occur beyond univariate statistical extremes.
"""

from __future__ import annotations

import numpy as np


def detect_multivariate_outliers(
    matrix: np.ndarray,
    threshold_sigma: float = 3.0,
) -> np.ndarray:
    """Identify compound outlier events using Mahalanobis distance heuristic.

    Args:
        matrix: Multi-stressor observation matrix (samples x stressors).
        threshold_sigma: Critical standard deviation boundary.

    Returns:
        Boolean mask array of outlier rows.
    """
    if matrix.shape[0] < 2:
        return np.zeros(matrix.shape[0], dtype=bool)

    mean = np.mean(matrix, axis=0)
    centered = matrix - mean
    cov = np.cov(matrix, rowvar=False)
    # Add regularizer for numerical stability
    cov_reg = cov + np.eye(cov.shape[0]) * 1e-6
    inv_cov = np.linalg.pinv(cov_reg)
    left = np.dot(centered, inv_cov)
    distances = np.sqrt(np.sum(left * centered, axis=1))

    cutoff = np.median(distances) + threshold_sigma * (
        np.percentile(distances, 75) - np.percentile(distances, 25)
    )
    return distances > cutoff
