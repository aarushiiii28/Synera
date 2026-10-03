"""Multiple testing corrections."""

import numpy as np

def bh_fdr(p: np.ndarray) -> np.ndarray:
    """
    Benjamini-Hochberg FDR (q-values), NaN-safe.
    """
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    n = len(pv)
    
    if n == 0:
        return q
        
    order = np.argsort(pv)
    ranked = pv[order] * n / np.arange(1, n + 1)
    
    # ensure monotonic
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    
    out = np.empty(n)
    out[order] = np.clip(ranked, 0, 1)
    q[ok] = out
    
    return q
