"""Interpretable composite confidence score. It is NOT a probability.

    stat         mean of [1 - q/alpha (clipped), min(|effect|/1, 1), 1 if the CI excludes 0 else 0]
    replication  1.0 independent replication, 0.75 replication on later data, 0.5 same-cohort / internal replication, 0 otherwise
    robustness   share of methods that agree (parametric, GBM-SHAP, NID)
    trust        1 if security CLEAN-or-advisory, ledger chain valid and replay matches, else 0

Weights come from ``configs/settings.yaml``. ``trust == 0`` forces the score to 0 and BLOCKS the finding.
"""

from __future__ import annotations

import numpy as np

DEFAULT_WEIGHTS = {"stat": 0.35, "replication": 0.30, "robustness": 0.20, "trust": 0.15}


def compute_confidence(
    q: float,
    alpha: float,
    cohens_d: float,
    ci_excludes_zero: bool,
    evidence_level: str,
    replicated: bool,
    robustness: float,
    trust: int,
    weights: dict | None = None,
) -> dict:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({("replication" if k == "rep" else "robustness" if k == "rob" else k): v for k, v in weights.items()})

    q_score = max(0.0, 1.0 - (q / alpha)) if not np.isnan(q) else 0.0
    d_score = min(abs(cohens_d) / 1.0, 1.0) if not np.isnan(cohens_d) else 0.0
    stat_score = (q_score + d_score + (1.0 if ci_excludes_zero else 0.0)) / 3.0

    rep_score = 0.0
    if replicated:
        if evidence_level == "INDEPENDENT_REPLICATION":
            rep_score = 1.0
        elif evidence_level == "LATER_DATA_REPLICATION":
            rep_score = 0.75
        elif evidence_level in ("INTERNAL_REPLICATION", "CROSS_TISSUE_SAME_COHORT"):
            rep_score = 0.5

    score = (stat_score * w["stat"] + rep_score * w["replication"] + robustness * w["robustness"] + float(trust) * w["trust"])
    if trust == 0:
        score = 0.0
    return {
        "score": float(score),
        "components": {"stat": float(stat_score), "replication": float(rep_score),
                       "robustness": float(robustness), "trust": int(trust)},
        "weights": w,
        "is_blocked": trust == 0,
    }
