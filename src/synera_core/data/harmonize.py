"""Data harmonization, alignment, and matrix standardizer.

Harmonizes heterogeneous multi-stressor measurements onto consistent coordinate
frames and standardized data matrices.
"""

from __future__ import annotations

import pandas as pd


def standardize_matrix(
    df: pd.DataFrame,
    feature_cols: list[str],
    impute_strategy: str = "median",
) -> pd.DataFrame:
    """Standardize numeric feature columns using robust scaling.

    Args:
        df: Input pandas DataFrame.
        feature_cols: List of column names to standardize.
        impute_strategy: Strategy to handle missing values ('median' or 'zero').

    Returns:
        DataFrame with standardized feature columns.
    """
    result = df.copy()
    for col in feature_cols:
        if col not in result.columns:
            continue
        series = result[col].astype(float)
        if impute_strategy == "median":
            series = series.fillna(series.median())
        else:
            series = series.fillna(0.0)

        std = series.std()
        if std > 0:
            result[col] = (series - series.mean()) / std
        else:
            result[col] = series - series.mean()
    return result
