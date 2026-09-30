"""Statistical bootstrapping procedures for confidence interval estimation."""

from __future__ import annotations

from typing import Callable, Tuple
import numpy as np


def bootstrap_ci(
    data: np.ndarray,
    stat_fn: Callable[[np.ndarray], float],
    n_reps: int = 2000,
    ci_level: float = 0.95,
    seed: int = 20260929,
) -> Tuple[float, float, float]:
    """Calculate empirical percentile bootstrap confidence intervals.

    Args:
        data: Observed 1D or 2D dataset.
        stat_fn: Function mapping sample to scalar statistic.
        n_reps: Number of bootstrap resamples.
        ci_level: Confidence level (e.g. 0.95 for 95% CI).
        seed: Random generator seed for determinism.

    Returns:
        Tuple of (point_estimate, ci_lower, ci_upper).
    """
    rng = np.random.default_rng(seed)
    n = len(data)
    point_est = float(stat_fn(data))
    if n < 2:
        return point_est, point_est, point_est

    boot_stats = np.empty(n_reps)
    for i in range(n_reps):
        idx = rng.choice(n, size=n, replace=True)
        boot_stats[i] = stat_fn(data[idx])

    alpha = 1.0 - ci_level
    ci_lower = float(np.percentile(boot_stats, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(boot_stats, 100.0 * (1.0 - alpha / 2.0)))
    return point_est, ci_lower, ci_upper
