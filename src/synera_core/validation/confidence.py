"""Confidence scoring system."""

import numpy as np

def compute_confidence(
    q: float,
    alpha: float,
    cohens_d: float,
    ci_excludes_zero: bool,
    evidence_level: str,
    replicated: bool,
    robustness: float,
    trust: int,
    weights: dict = None
) -> dict:
    """
    Interpretable composite confidence score (NOT a probability).
    """
    if weights is None:
        weights = {"stat": 0.4, "rep": 0.4, "rob": 0.2}
        
    # stat component
    q_score = max(0.0, 1.0 - (q / alpha)) if not np.isnan(q) else 0.0
    d_score = min(abs(cohens_d) / 1.0, 1.0) if not np.isnan(cohens_d) else 0.0
    ci_score = 1.0 if ci_excludes_zero else 0.0
    stat_score = (q_score + d_score + ci_score) / 3.0
    
    # replication component
    rep_score = 0.0
    if replicated:
        if evidence_level == "INDEPENDENT_REPLICATION":
            rep_score = 1.0
        elif evidence_level in ["INTERNAL_REPLICATION", "CROSS_TISSUE_SAME_COHORT"]:
            rep_score = 0.5
            
    # overall
    score = (stat_score * weights["stat"] + 
             rep_score * weights["rep"] + 
             robustness * weights["rob"])
             
    if trust == 0:
        score = 0.0
        
    return {
        "score": score,
        "components": {
            "stat": stat_score,
            "replication": rep_score,
            "robustness": robustness,
            "trust": trust
        },
        "is_blocked": (trust == 0)
    }
