"""Interaction classification logic."""

import numpy as np

def classify_factorial(b_A: float, b_B: float, b_AB: float, q: float, alpha: float = 0.05, min_abs_effect: float = 0.5) -> dict:
    """
    Classify the interaction type.
    
    On a log2 scale, "additive" means multiplicative independence in fold change.
    
    Types: synergistic | antagonistic | none.
    s = b_A + b_B (additive expectation).
    If q >= alpha or |b_AB| < min_abs_effect -> none.
    synergistic if s * b_AB > 0 (amplifies the additive expectation) else antagonistic (dampens it).
    reversal = sign(s + b_AB) != sign(s) and s != 0.
    interaction_only = |s| < 0.25 * |b_AB|.
    """
    s = b_A + b_B
    
    if np.isnan(q) or q >= alpha or abs(b_AB) < min_abs_effect:
        itype = "none"
    else:
        if s * b_AB > 0:
            itype = "synergistic"
        else:
            itype = "antagonistic"
            
    # For reversal, define sign carefully to avoid 0 issues.
    sign_s = 1 if s > 0 else (-1 if s < 0 else 0)
    sign_obs = 1 if (s + b_AB) > 0 else (-1 if (s + b_AB) < 0 else 0)
    
    reversal = (sign_obs != sign_s) and (s != 0)
    interaction_only = abs(s) < 0.25 * abs(b_AB)
    
    return {
        "type": itype,
        "reversal": reversal,
        "interaction_only": interaction_only
    }
