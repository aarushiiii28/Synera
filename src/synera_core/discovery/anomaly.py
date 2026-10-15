"""Anomaly detection for sample outlier flagging."""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.covariance import MinCovDet

def detect_anomalies(X: pd.DataFrame, contamination: float = 0.05) -> dict:
    """
    IsolationForest + MinCovDet.
    """
    # handle NaNs
    X_clean = X.fillna(X.median())
    
    # IF
    iso = IsolationForest(contamination=contamination, random_state=42)
    iso_preds = iso.fit_predict(X_clean)
    iso_outliers = X.index[iso_preds == -1].tolist()
    
    # MCD (requires n_samples > n_features, fallback if not)
    mcd_outliers = []
    if X_clean.shape[0] > X_clean.shape[1] + 1:
        try:
            mcd = MinCovDet(random_state=42).fit(X_clean)
            dist = mcd.mahalanobis(X_clean)
            thresh = np.percentile(dist, 100 * (1 - contamination))
            mcd_outliers = X.index[dist > thresh].tolist()
        except (ValueError, np.linalg.LinAlgError):   # singular covariance: the robust detector is simply skipped
            pass
            
    # return union
    union = list(set(iso_outliers + mcd_outliers))
    
    return {
        "iso_outliers": iso_outliers,
        "mcd_outliers": mcd_outliers,
        "combined": union
    }
