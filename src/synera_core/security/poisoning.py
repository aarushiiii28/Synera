import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.ensemble import IsolationForest
from sklearn.covariance import MinCovDet
from sklearn.neighbors import NearestNeighbors
from scipy import stats
import hashlib
from synera_core.validation.multitest import bh_fdr

class SecurityReport:
    def __init__(self):
        self.checks: List[Dict[str, Any]] = []
        self.suspicion_scores = None
        self.status = "CLEAN"
        
    def add_check(self, name: str, status: str, score: float, detail: str, evidence: Any = None):
        self.checks.append({
            "name": name,
            "status": status,
            "score": score,
            "detail": detail,
            "evidence": evidence
        })
        if status == "FAIL":
            self.status = "COMPROMISED"
        elif status == "WARN" and self.status == "CLEAN":
            # If there's already a WARN, multiple WARNs might make it SUSPICIOUS
            warn_count = sum(1 for c in self.checks if c["status"] == "WARN")
            if warn_count > 1:
                self.status = "SUSPICIOUS"
            else:
                self.status = "CLEAN" # still clean with 1 warn

def calculate_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Calculate Population Stability Index."""
    def scale_range(arr):
        return (arr - arr.min()) / (arr.max() - arr.min() + 1e-9)
    
    breaks = np.linspace(0, 1, buckets + 1)
    expected_pct = np.histogram(scale_range(expected), breaks)[0] / len(expected)
    actual_pct = np.histogram(scale_range(actual), breaks)[0] / len(actual)
    
    expected_pct = np.clip(expected_pct, 1e-4, 1.0)
    actual_pct = np.clip(actual_pct, 1e-4, 1.0)
    
    psi_values = (expected_pct - actual_pct) * np.log(expected_pct / actual_pct)
    return float(np.sum(psi_values))

def scan_dataset(df_or_expr: pd.DataFrame, meta: Optional[pd.DataFrame] = None, 
                 baseline: Optional[Dict[str, Any]] = None, 
                 ranges: Optional[Dict[str, tuple]] = None) -> SecurityReport:
    """
    Ensemble poisoning and anomaly detection.
    """
    report = SecurityReport()
    report.suspicion_scores = np.zeros(len(df_or_expr))
    
    # Check 1: Schema & physical-range validation
    if ranges:
        out_of_bounds = 0
        for col, (vmin, vmax) in ranges.items():
            if col in df_or_expr.columns:
                vals = df_or_expr[col].dropna()
                violations = (vals < vmin) | (vals > vmax)
                if violations.any():
                    out_of_bounds += violations.sum()
        if out_of_bounds > 0:
            report.add_check("physical_range", "FAIL", float(out_of_bounds), f"{out_of_bounds} values out of bounds")
        else:
            report.add_check("physical_range", "PASS", 0.0, "All values within physical ranges")
            
    # Check 2: Duplicates / Near-duplicates
    # Exact hash
    hashes = df_or_expr.apply(lambda row: hashlib.md5(row.values.tobytes()).hexdigest(), axis=1)
    exact_dups = hashes.duplicated(keep=False).sum()
    if exact_dups > 0:
        report.add_check("duplicates", "FAIL", float(exact_dups), f"{exact_dups} exact duplicate rows found")
    else:
        report.add_check("duplicates", "PASS", 0.0, "No exact duplicates")
        
    # Check 3: Sample-level outliers
    try:
        X = df_or_expr.select_dtypes(include=[np.number]).fillna(df_or_expr.mean(numeric_only=True)).values
        
        # Isolation Forest
        iso = IsolationForest(contamination=0.05, random_state=42)
        iso_preds = iso.fit_predict(X)
        iso_scores = -iso.score_samples(X)
        
        # MCD (Robust Mahalanobis)
        if X.shape[0] > X.shape[1] and X.shape[1] < 50:
            mcd = MinCovDet(random_state=42).fit(X)
            mcd_dist = mcd.mahalanobis(X)
            mcd_scores = mcd_dist / np.median(mcd_dist)
        else:
            mcd_scores = np.zeros(X.shape[0])
            
        # Very simple Autoencoder logic using PyTorch
        import torch
        import torch.nn as nn
        import torch.optim as optim
        torch.manual_seed(42)
        n_features = X.shape[1]
        n_hidden = max(2, n_features // 2)
        model = nn.Sequential(
            nn.Linear(n_features, n_hidden),
            nn.ReLU(),
            nn.Linear(n_hidden, n_features)
        )
        opt = optim.Adam(model.parameters(), lr=0.01)
        loss_fn = nn.MSELoss()
        X_t = torch.tensor(X, dtype=torch.float32)
        for _ in range(50):
            opt.zero_grad()
            out = model(X_t)
            loss = loss_fn(out, X_t)
            loss.backward()
            opt.step()
            
        with torch.no_grad():
            X_rec = model(X_t).numpy()
            
        rec_errors = np.mean((X - X_rec)**2, axis=1)
        rec_scores = rec_errors / (np.median(rec_errors) + 1e-9)
        
        # Consensus
        consensus = (iso_scores / np.median(iso_scores)) + mcd_scores + rec_scores
        report.suspicion_scores += consensus
        
        n_outliers = np.sum(iso_preds == -1)
        if n_outliers > 0:
            report.add_check("outliers", "WARN", float(n_outliers), f"{n_outliers} sample-level outliers detected")
        else:
            report.add_check("outliers", "PASS", 0.0, "No significant sample outliers")
    except Exception as e:
        report.add_check("outliers", "WARN", 1.0, f"Outlier check failed: {str(e)}")

    # Check 4: Distribution drift
    if baseline is not None:
        drifts = 0
        for col, base_stats in baseline.items():
            if col in df_or_expr.columns:
                vals = df_or_expr[col].dropna().values
                if len(vals) > 5 and len(base_stats.get('sample', [])) > 5:
                    ks_stat, p = stats.ks_2samp(vals, base_stats['sample'])
                    psi = calculate_psi(np.array(base_stats['sample']), vals)
                    if p < 0.05 and psi > 0.2:
                        drifts += 1
        if drifts > 0:
            report.add_check("distribution_drift", "WARN", float(drifts), f"{drifts} features show significant drift vs baseline")
        else:
            report.add_check("distribution_drift", "PASS", 0.0, "No significant distribution drift")

    # Check 5: Label-flip / Metadata-consistency
    if meta is not None:
        try:
            X = df_or_expr.select_dtypes(include=[np.number]).fillna(df_or_expr.mean(numeric_only=True)).values
            nn = NearestNeighbors(n_neighbors=min(5, len(X)-1))
            nn.fit(X)
            distances, indices = nn.kneighbors(X)
            
            flips = 0
            for col in meta.columns:
                if pd.api.types.is_numeric_dtype(meta[col]) and meta[col].nunique() == 2:
                    y = meta[col].values
                    for i in range(len(y)):
                        neighbor_labels = y[indices[i]]
                        if np.mean(neighbor_labels == y[i]) < 0.2: # strongly disagrees
                            flips += 1
                            report.suspicion_scores[i] += 5.0
            
            if flips > 0:
                report.add_check("label_flip", "WARN", float(flips), f"{flips} samples have labels disagreeing with neighbors")
            else:
                report.add_check("label_flip", "PASS", 0.0, "Labels consistent with expression space")
        except Exception as e:
            pass
            
    # Check 6: Temporal sanity
    date_cols = [c for c in df_or_expr.columns if 'date' in c.lower() or 'time' in c.lower()]
    if date_cols:
        for dc in date_cols:
            try:
                dates = pd.to_datetime(df_or_expr[dc])
                if 'city' in df_or_expr.columns:
                    # check per city
                    is_mono = df_or_expr.groupby('city')[dc].apply(lambda x: pd.to_datetime(x).is_monotonic_increasing).all()
                else:
                    is_mono = dates.is_monotonic_increasing
                    
                if not is_mono:
                    report.add_check("temporal_sanity", "FAIL", 1.0, f"Timestamps in {dc} are not monotonic")
                    break
            except:
                pass
        else:
            report.add_check("temporal_sanity", "PASS", 0.0, "Timestamps strictly monotonic")

    return report
