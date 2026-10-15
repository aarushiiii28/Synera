"""LightGBM + SHAP pairwise interaction strengths (an independent second opinion).

The model is fitted on the stressors plus nuisance covariates (city code, seasonality) so that
city and season structure is not mistaken for stressor interaction. The strength of a pair is the
mean absolute SHAP interaction value (``TreeExplainer.shap_interaction_values``), symmetrised.

An optional permutation reference (``n_permutations > 0``) refits the model on
``additive prediction + block-permuted residuals`` (Freedman-Lane style) to give a null
distribution of the pairwise strengths; it is expensive and off by default.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def _fit(X: np.ndarray, y: np.ndarray, seed: int, n_estimators: int):
    import lightgbm as lgb

    return lgb.LGBMRegressor(
        n_estimators=n_estimators, learning_rate=0.05, num_leaves=15, max_depth=4,
        min_child_samples=20, subsample=0.8, subsample_freq=1, colsample_bytree=0.9,
        reg_lambda=1.0, random_state=seed, n_jobs=1, verbose=-1,
    ).fit(X, y)


def _interaction_matrix(model, X: np.ndarray, n_stressors: int, max_rows: int, seed: int) -> np.ndarray:
    import shap

    rng = np.random.default_rng(seed)
    idx = np.arange(len(X)) if len(X) <= max_rows else np.sort(rng.choice(len(X), max_rows, replace=False))
    vals = shap.TreeExplainer(model).shap_interaction_values(X[idx])  # (n, p, p)
    mat = np.abs(vals).mean(axis=0)
    mat = 0.5 * (mat + mat.T)
    out = mat[:n_stressors, :n_stressors].copy()
    np.fill_diagonal(out, 0.0)
    return out


def run_gbm_interactions(X: pd.DataFrame, y: np.ndarray, stressors: Sequence[str] | None = None,
                         seed: int = 0, n_estimators: int = 250, max_shap_rows: int = 1500,
                         n_permutations: int = 0, city_slices: list[slice] | None = None) -> dict:
    """Return the pairwise SHAP-interaction matrix over ``stressors`` (all columns if ``None``).

    Columns of ``X`` that are not in ``stressors`` are used as nuisance covariates only.
    """
    cols = list(X.columns)
    stressors = list(stressors) if stressors is not None else cols
    order = stressors + [c for c in cols if c not in stressors]
    Xv = X[order].to_numpy(float)
    yv = np.asarray(y, float)
    k = len(stressors)

    # Contiguous-block hold-out R^2 (last 20% of rows): honest about overfitting, no row shuffling.
    cut = int(len(Xv) * 0.8)
    holdout = _fit(Xv[:cut], yv[:cut], seed, n_estimators)
    pred = holdout.predict(Xv[cut:])
    ss_res = float(np.sum((yv[cut:] - pred) ** 2))
    ss_tot = float(np.sum((yv[cut:] - yv[cut:].mean()) ** 2)) + 1e-12
    r2 = 1.0 - ss_res / ss_tot

    model = _fit(Xv, yv, seed, n_estimators)
    matrix = _interaction_matrix(model, Xv, k, max_shap_rows, seed)

    null_max = None
    if n_permutations > 0:
        rng = np.random.default_rng(seed + 1)
        import lightgbm as lgb

        add = lgb.LGBMRegressor(n_estimators=n_estimators, learning_rate=0.05, max_depth=2, num_leaves=4,
                                interaction_constraints=[[i] for i in range(Xv.shape[1])],
                                random_state=seed, n_jobs=1, verbose=-1).fit(Xv, yv)
        fitted = add.predict(Xv)
        resid = yv - fitted
        slices = city_slices or [slice(0, len(yv))]
        null_max = []
        for _ in range(n_permutations):
            rp = resid.copy()
            for sl in slices:
                seg = resid[sl]
                L = max(5, min(30, len(seg) // 10))
                nb = int(np.ceil(len(seg) / L))
                starts = rng.integers(0, len(seg) - L + 1, nb)
                rp[sl] = np.concatenate([seg[s:s + L] for s in starts])[:len(seg)]
            m = _fit(Xv, fitted + rp, seed, n_estimators)
            null_max.append(float(_interaction_matrix(m, Xv, k, max_shap_rows, seed).max()))

    pairs = []
    for i in range(k):
        for j in range(i + 1, k):
            p_null = None
            if null_max is not None:
                p_null = float((1 + np.sum(np.array(null_max) >= matrix[i, j])) / (1 + len(null_max)))
            pairs.append({"a": stressors[i], "b": stressors[j], "strength": float(matrix[i, j]),
                          "p_perm": p_null})
    pairs.sort(key=lambda d: -d["strength"])
    for r, d in enumerate(pairs, 1):
        d["rank"] = r
    return {
        "interaction_matrix": matrix, "stressors": stressors, "ranked_pairs": pairs,
        "holdout_r2": float(r2), "method": "LightGBM_SHAP",
        "n_permutations": int(n_permutations),
    }
