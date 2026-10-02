"""Benchmark evaluation metrics (Precision, Recall, FDR)."""

from __future__ import annotations


def evaluate_interaction_recovery(
    discovered_pairs: list[tuple[str, str]],
    planted_pairs: list[tuple[str, str]],
) -> dict[str, float]:
    """Calculate discovery precision, recall, and false discovery proportion.

    Args:
        discovered_pairs: List of predicted interaction pairs.
        planted_pairs: Ground-truth planted interaction pairs.

    Returns:
        Dictionary of precision, recall, f1, and fdr scores.
    """
    discovered_norm: set[tuple[str, str]] = {
        tuple(sorted(pair)) for pair in discovered_pairs  # type: ignore[misc]
    }
    planted_norm: set[tuple[str, str]] = {
        tuple(sorted(pair)) for pair in planted_pairs  # type: ignore[misc]
    }

    if not discovered_norm:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "fdr": 0.0,
        }

    tp = len(discovered_norm & planted_norm)
    fp = len(discovered_norm - planted_norm)
    fn = len(planted_norm - discovered_norm)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fdr = fp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fdr": round(fdr, 4),
    }
