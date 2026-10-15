"""Bootstrap confidence intervals."""

import numpy as np

def factorial_bootstrap_ci(
    Y: np.ndarray, 
    X: np.ndarray, 
    n_boot: int = 100, 
    seed: int = 42, 
    alpha: float = 0.05
) -> tuple[np.ndarray, np.ndarray]:
    """
    Vectorized case bootstrap for factorial OLS interaction coefficient.
    
    Y: (n_samples, n_features)
    X: (n_samples, p)
    Returns: (ci_low, ci_high) arrays of length n_features.
    """
    rng = np.random.default_rng(seed)
    n, p = X.shape
    n_features = Y.shape[1]
    
    # Pre-allocate boot array: (n_boot, n_features)
    boot_betas = np.zeros((n_boot, n_features))
    
    for i in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        X_b = X[idx]
        Y_b = Y[idx]
        
        # Check rank
        try:
            XtX_inv = np.linalg.pinv(X_b.T @ X_b)
            beta = XtX_inv @ X_b.T @ Y_b
            boot_betas[i, :] = beta[3]
        except np.linalg.LinAlgError:
            boot_betas[i, :] = np.nan
            
    # Percentile CI
    ci_low = np.nanpercentile(boot_betas, 100 * (alpha / 2), axis=0)
    ci_high = np.nanpercentile(boot_betas, 100 * (1 - alpha / 2), axis=0)
    
    return ci_low, ci_high
