"""Multiple testing corrections and false discovery rate (FDR) control."""

from __future__ import annotations

from typing import Tuple
import numpy as np


def benjamini_hochberg(
    p_values: np.ndarray | list[float],
    alpha: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray]:
    """Perform Benjamini-Hochberg False Discovery Rate (FDR) procedure.

    Args:
        p_values: Array of unadjusted p-values in [0, 1].
        alpha: Target family-wise FDR threshold.

    Returns:
        Tuple of (reject_mask, q_values).
    """
    pvals = np.asarray(p_values, dtype=float)
    n = len(pvals)
    if n == 0:
        return np.array([], dtype=bool), np.array([], dtype=float)

    sorted_indices = np.argsort(pvals)
    sorted_pvals = pvals[sorted_indices]

    # q_i = p_i * n / rank
    ranks = np.arange(1, n + 1)
    q_vals = sorted_pvals * n / ranks
    # Enforce monotonicity from right to left
    q_vals = np.minimum.accumulate(q_vals[::-1])[::-1]
    q_vals = np.clip(q_vals, 0.0, 1.0)

    # Reorder back to original indices
    orig_q_vals = np.empty_like(q_vals)
    orig_q_vals[sorted_indices] = q_vals

    reject = orig_q_vals <= alpha
    return reject, orig_q_vals
