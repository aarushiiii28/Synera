"""Factorial OLS with simplified empirical-Bayes variance moderation."""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Sequence

def factorial_interaction(
    Y: pd.DataFrame,
    meta: pd.DataFrame,
    a: str,
    b: str,
    covariates: Sequence[str] = (),
    moderate: bool = True,
    prior_df: float = 4.0
) -> pd.DataFrame:
    """
    Compute vectorized per-feature OLS with an A x B interaction.
    
    Y: samples x features (log2 scale).
    meta: sample metadata containing factors `a`, `b` and any `covariates`.
          The order of rows in meta must match columns in Y if Y is features x samples.
          Wait, prompt says "Y: samples x features". Let's assume Y has shape (n_samples, n_features).
    a: name of binary factor A in meta.
    b: name of binary factor B in meta.
    covariates: optional list of covariates.
    moderate: whether to use simplified empirical-Bayes variance moderation (limma approximation).
    
    Returns: DataFrame indexed by features, with columns:
        b_A, b_B, b_AB, se_AB, t_AB, df, p_AB, additive_expected, observed_combined, sigma, cohens_d_int
    """
    # Ensure dimensions match
    if Y.shape[0] != len(meta):
        raise ValueError("Y (samples x features) row count must match meta row count.")
        
    A = meta[a].to_numpy(float)
    B = meta[b].to_numpy(float)
    
    # Check minimum 2 replicates per cell
    cell_counts = meta.groupby([a, b]).size()
    if cell_counts.min() < 2:
        raise ValueError(f"Require minimum 2 replicates per cell. Got: {cell_counts.to_dict()}")
        
    # Design matrix X: [Intercept, A, B, A*B, ...covariates]
    cols = [np.ones_like(A), A, B, A * B]
    for c in covariates:
        cols.append(meta[c].to_numpy(float))
        
    X = np.column_stack(cols)
    n, p = X.shape
    df_res = n - p
    
    if df_res < 1:
        raise ValueError("No residual degrees of freedom.")
        
    XtX_inv = np.linalg.pinv(X.T @ X)
    Yv = Y.to_numpy(float)
    
    # beta is (p x n_features)
    beta = XtX_inv @ X.T @ Yv
    
    # residuals
    resid = Yv - (X @ beta)
    
    # residual variance per feature
    s2 = (resid ** 2).sum(axis=0) / df_res
    
    if moderate:
        # Simplified empirical Bayes (limma approximation)
        s0 = np.nanmedian(s2)
        s2_t = (prior_df * s0 + df_res * s2) / (prior_df + df_res)
        d = df_res + prior_df
    else:
        s2_t = s2
        d = df_res
        
    # Interaction term is at index 3
    with np.errstate(divide="ignore", invalid="ignore"):
        se_int = np.sqrt(XtX_inv[3, 3] * s2_t)
        t_int = beta[3] / se_int
        
    p_int = 2 * stats.t.sf(np.abs(t_int), d)
    
    # Build output dataframe
    # Features with s2==0 get NaN p_int
    mask_zero = (s2 == 0)
    p_int[mask_zero] = np.nan
    t_int[mask_zero] = np.nan
    
    sigma = np.sqrt(s2_t)
    cohens_d = beta[3] / sigma
    
    additive_expected = beta[1] + beta[2]
    observed_combined = beta[1] + beta[2] + beta[3]
    
    out_df = pd.DataFrame({
        "b_A": beta[1],
        "b_B": beta[2],
        "b_AB": beta[3],
        "se_AB": se_int,
        "t_AB": t_int,
        "df": np.full(Y.shape[1], d),
        "p_AB": p_int,
        "additive_expected": additive_expected,
        "observed_combined": observed_combined,
        "sigma": sigma,
        "cohens_d_int": cohens_d
    }, index=Y.columns)
    
    return out_df
