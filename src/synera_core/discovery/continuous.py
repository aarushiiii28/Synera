"""Continuous interactions (nested model ladder)."""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm
from scipy import stats

def continuous_interaction(
    y_col: str,
    a_col: str,
    b_col: str,
    data: pd.DataFrame,
    covariates: list[str] = None,
    k: int = 3,
    alpha: float = 0.05
) -> dict:
    """
    Nested model ladder for continuous stressors.
    
    M0: additive smooth (bs)
    M1: bilinear interaction added
    M2: full tensor surface
    """
    if covariates is None:
        covariates = []
        
    # Standardize a and b for numerical stability
    data = data.copy()
    a_std = (data[a_col] - data[a_col].mean()) / data[a_col].std()
    b_std = (data[b_col] - data[b_col].mean()) / data[b_col].std()
    
    data['A'] = a_std
    data['B'] = b_std
    
    cov_str = ("+ " + " + ".join(covariates)) if covariates else ""
    
    # Formulas
    f0 = f"{y_col} ~ bs(A, df={k}) + bs(B, df={k}) {cov_str}"
    f1 = f"{y_col} ~ bs(A, df={k}) + bs(B, df={k}) + A:B {cov_str}"
    f2 = f"{y_col} ~ bs(A, df={k}) * bs(B, df={k}) {cov_str}"
    
    # Fit
    m0 = smf.ols(f0, data=data).fit()
    m1 = smf.ols(f1, data=data).fit()
    m2 = smf.ols(f2, data=data).fit()
    
    # ANOVA F-tests
    anova_1 = sm.stats.anova_lm(m0, m1)
    p_bilinear = anova_1["Pr(>F)"].iloc[1]
    
    anova_2 = sm.stats.anova_lm(m1, m2)
    p_nonlinear = anova_2["Pr(>F)"].iloc[1]
    
    # Classification
    if not np.isnan(p_nonlinear) and p_nonlinear < alpha:
        itype = "nonlinear"
    elif not np.isnan(p_bilinear) and p_bilinear < alpha:
        # Check synergy vs antagonism at upper quartile
        q75_A = data['A'].quantile(0.75)
        q75_B = data['B'].quantile(0.75)
        
        # Predict at q75 vs mean (0)
        # We want to see if the interaction term A:B coef shares sign with the main effects sum
        coef_AB = m1.params.get("A:B", 0.0)
        
        # approximate main effect sign by predicting A=q75, B=0 and A=0, B=q75
        base_covs = {}
        for c in covariates:
            base_covs[c] = data[c].mean() if pd.api.types.is_numeric_dtype(data[c]) else data[c].mode()[0]
            
        pred_base = m1.predict(pd.DataFrame({'A':[0], 'B':[0], **base_covs})).iloc[0]
        pred_A = m1.predict(pd.DataFrame({'A':[q75_A], 'B':[0], **base_covs})).iloc[0]
        pred_B = m1.predict(pd.DataFrame({'A':[0], 'B':[q75_B], **base_covs})).iloc[0]
        
        main_eff = (pred_A - pred_base) + (pred_B - pred_base)
        
        if main_eff * coef_AB > 0:
            itype = "synergistic"
        else:
            itype = "antagonistic"
    else:
        itype = "none"
        
    # Generate 40x40 grid for UI
    a_grid = np.linspace(data['A'].min(), data['A'].max(), 40)
    b_grid = np.linspace(data['B'].min(), data['B'].max(), 40)
    AA, BB = np.meshgrid(a_grid, b_grid)
    grid_df = pd.DataFrame({'A': AA.flatten(), 'B': BB.flatten()})
    for c in covariates:
        if pd.api.types.is_numeric_dtype(data[c]):
            grid_df[c] = data[c].mean()
        else:
            grid_df[c] = data[c].mode()[0]
        
    z_additive = m0.predict(grid_df).values.reshape(40, 40)
    z_full = m2.predict(grid_df).values.reshape(40, 40)
    y_sd = data[y_col].std()
    z_gap = (z_full - z_additive) / (y_sd + 1e-9)
    
    return {
        "p_bilinear": p_bilinear,
        "p_nonlinear": p_nonlinear,
        "type": itype,
        "grid_a": a_grid,
        "grid_b": b_grid,
        "z_additive": z_additive,
        "z_full": z_full,
        "z_gap": z_gap,
        "models": (m0, m1, m2)
    }
