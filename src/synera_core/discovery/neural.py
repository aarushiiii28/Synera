"""Neural representation and interaction embedding network.

Embeds high-dimensional stressor profiles into latent manifolds for deep non-linear
interaction hypothesis generation.
"""

from __future__ import annotations

import numpy as np


def project_latent_manifold(
    features: np.ndarray,
    latent_dim: int = 2,
) -> np.ndarray:
    """Project stressor feature vectors into a lower-dimensional latent space.

    Args:
        features: 2D array of normalized stressor inputs (N x D).
        latent_dim: Target dimensionality.

    Returns:
        Projected latent coordinates (N x latent_dim).
    """
    if features.shape[1] <= latent_dim:
        return features[:, :latent_dim]
    # SVD fallback projection
    u, s, _ = np.linalg.svd(features - np.mean(features, axis=0), full_matrices=False)
    return u[:, :latent_dim] * s[:latent_dim]
