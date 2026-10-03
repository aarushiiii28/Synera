"""Replication validation."""

import pandas as pd
import numpy as np
from scipy import stats
from .multitest import bh_fdr

def replicate(disc: pd.DataFrame, rep: pd.DataFrame, alpha_disc=0.05, alpha_rep=0.05, evidence_level="CROSS_TISSUE_SAME_COHORT") -> dict:
    """
    Join on feature. Take discovery hits (q<alpha_disc). For each: sign concordance of b_AB;
    one-sided replication p = t.sf(sign_d * t_r, df_r); BH over the hits -> q_rep.
    Report n_hits, n_shared, concordance, binomial test p vs 0.5, replication_rate, pi1 (Storey).
    """
    # Join on index (features)
    merged = disc.join(rep, lsuffix="_d", rsuffix="_r", how="inner")
    
    hits = merged[merged["q_AB_d"] < alpha_disc].copy()
    n_hits = len(disc[disc["q_AB_d"] < alpha_disc])
    n_shared = len(hits)
    
    if n_shared == 0:
        return {
            "evidence_level": evidence_level,
            "n_hits": n_hits,
            "n_shared": 0,
            "concordance": np.nan,
            "binomial_p": np.nan,
            "replication_rate": 0.0,
            "pi1": np.nan,
            "flags": pd.Series(dtype=bool)
        }
        
    # Sign concordance
    sign_d = np.sign(hits["b_AB_d"])
    sign_r = np.sign(hits["b_AB_r"])
    concordant = (sign_d == sign_r)
    concordance = concordant.mean()
    
    binom_p = stats.binomtest(concordant.sum(), n_shared, 0.5, alternative="greater").pvalue
    
    # One-sided replication p
    t_r = hits["t_AB_r"]
    df_r = hits["df_r"]
    p_rep = stats.t.sf(sign_d * t_r, df_r)
    
    # BH over hits
    q_rep = bh_fdr(p_rep)
    
    # Replication rate
    replicated = (q_rep < alpha_rep) & concordant
    rep_rate = replicated.mean()
    
    # Storey pi1 estimate (simplified)
    # lambda = 0.5
    pi0 = np.mean(p_rep > 0.5) / 0.5
    pi1 = max(0.0, min(1.0, 1.0 - pi0))
    
    flags = pd.Series(replicated, index=hits.index)
    
    return {
        "evidence_level": evidence_level,
        "n_hits": n_hits,
        "n_shared": n_shared,
        "concordance": concordance,
        "binomial_p": binom_p,
        "replication_rate": rep_rate,
        "pi1": pi1,
        "flags": flags
    }
