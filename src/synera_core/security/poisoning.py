"""Ensemble poisoning / anomaly detection for tabular datasets.

Design rules
------------
* **Calibrated, not guessed.** Every statistical detector scores rows and flags those above the 99th
  percentile of the same score on a *registered baseline* (``Baseline``). A detector only raises a
  ``WARN`` when the number of flagged rows is implausible under the clean 1% rate (binomial test at
  the 0.1% level). Without a baseline the detectors fall back to robust in-sample cutoffs.
* **Only integrity-critical checks can block.** ``physical_range`` and ``temporal_sanity`` are
  ``blocking`` (a FAIL makes the report ``COMPROMISED``). Every statistical detector is advisory:
  it produces ``WARN`` + a score and marks the report ``SUSPICIOUS``, never ``COMPROMISED``.
  The cryptographic hash check lives in :mod:`synera_core.security.integrity`.
* **Honest about applicability.** The label-flip check says so when the labels carry no separable
  structure in feature space (it cannot be informative there).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.covariance import MinCovDet
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import NearestNeighbors

from synera_core.validation.multitest import bh_fdr

BLOCKING_CHECKS = {"physical_range", "temporal_sanity"}
CLEAN_RATE = 0.01          # share of clean rows above the 99th-percentile cutoff
FLAG_LEVEL = 0.999         # binomial confidence required before a detector raises WARN
DESIGN_ALLOWANCE = 2.5     # rows of a daily panel are autocorrelated, so flagged counts are overdispersed

# Physical plausibility ranges used when the caller supplies none (column name -> (min, max)).
DEFAULT_RANGES: Dict[str, tuple] = {
    "tmax": (-60.0, 60.0), "tmean": (-60.0, 60.0), "rh": (0.0, 100.0),
    "heat_index": (-60.0, 80.0), "precip": (0.0, 2000.0), "pm25": (0.0, 2000.0),
    "pm10": (0.0, 3000.0), "o3": (0.0, 1000.0), "no2": (0.0, 1000.0),
    "uv": (0.0, 20.0), "wind": (0.0, 400.0),
}


class SecurityReport:
    """Container for per-check results and the overall verdict."""

    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.suspicion_scores: Optional[np.ndarray] = None
        self.status = "CLEAN"

    def add_check(self, name: str, status: str, score: float, detail: str, evidence: Any = None) -> None:
        blocking = name in BLOCKING_CHECKS
        self.checks.append({"name": name, "status": status, "score": float(score), "detail": detail,
                            "blocking": blocking, "evidence": evidence})
        if status == "FAIL" and blocking:
            self.status = "COMPROMISED"
        elif status in ("WARN", "FAIL") and self.status == "CLEAN":
            self.status = "SUSPICIOUS"

    def to_dict(self) -> dict:
        return {"status": self.status, "checks": self.checks}


# --------------------------------------------------------------------------- #
# Baseline
# --------------------------------------------------------------------------- #
def _plausible_defaults(df: pd.DataFrame) -> Dict[str, tuple]:
    """Default physical ranges for columns that look like physical units.

    A column whose median sits at the very edge of its range (e.g. a z-scored relative humidity, median ~0
    against a 0-100 range) is not in physical units, so the range does not apply to it.
    """
    out: Dict[str, tuple] = {}
    for c, (lo, hi) in DEFAULT_RANGES.items():
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            med, span = float(df[c].median()), hi - lo
            if lo + 0.02 * span <= med <= hi - 0.02 * span:
                out[c] = (lo, hi)
    return out


def _binom_cutoff(n: int, rate: float = CLEAN_RATE) -> int:
    """Largest flagged count still consistent with the clean rate (binomial, widened for autocorrelation)."""
    return max(2, int(stats.binom.ppf(FLAG_LEVEL, n, rate)), int(np.ceil(DESIGN_ALLOWANCE * rate * n)))


def _knn_agreement(Z: np.ndarray, y: np.ndarray, k: int = 5) -> np.ndarray:
    """Share of each row's k nearest neighbours (feature space) that carry the same label."""
    k = min(k, len(Z) - 1)
    _, idx = NearestNeighbors(n_neighbors=k + 1).fit(Z).kneighbors(Z)
    return (y[idx[:, 1:]] == y[:, None]).mean(axis=1)


def calculate_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index using quantile bins of the expected sample."""
    expected, actual = np.asarray(expected, float), np.asarray(actual, float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, buckets + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.clip(np.histogram(expected, edges)[0] / len(expected), 1e-4, 1.0)
    a = np.clip(np.histogram(actual, edges)[0] / len(actual), 1e-4, 1.0)
    return float(np.sum((e - a) * np.log(e / a)))


def _fit_autoencoder(Z: np.ndarray, seed: int = 0, epochs: int = 200):
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    p = Z.shape[1]
    h = max(2, p // 2)
    net = nn.Sequential(nn.Linear(p, h), nn.Tanh(), nn.Linear(h, p))
    opt = torch.optim.Adam(net.parameters(), lr=0.01)
    X = torch.tensor(Z, dtype=torch.float32)
    for _ in range(epochs):
        opt.zero_grad()
        loss = ((net(X) - X) ** 2).mean()
        loss.backward()
        opt.step()
    return net


def _ae_scores(net, Z: np.ndarray) -> np.ndarray:
    import torch

    with torch.no_grad():
        X = torch.tensor(Z, dtype=torch.float32)
        return ((net(X) - X) ** 2).mean(dim=1).numpy()


@dataclass
class Baseline:
    """Registered reference statistics of a clean dataset (fit once, reuse for every scan)."""

    columns: List[str]
    center: np.ndarray
    scale: np.ndarray
    samples: Dict[str, np.ndarray]
    ranges: Dict[str, tuple]
    iso: IsolationForest
    iso_cut: float
    mcd: Optional[MinCovDet]
    mcd_cut: float
    ae: Any
    ae_cut: float
    n_rows: int
    seed: int = 0
    label_rates: Dict[str, float] = field(default_factory=dict)
    _digest: str = field(default="", repr=False)

    @classmethod
    def from_frame(cls, df: pd.DataFrame, ranges: Optional[Dict[str, tuple]] = None, seed: int = 0,
                   meta: Optional[pd.DataFrame] = None) -> "Baseline":
        num = df.select_dtypes(include=[np.number])
        num = num.loc[:, num.nunique() > 1]
        cols = list(num.columns)
        X = num.fillna(num.median()).to_numpy(float)
        center = np.median(X, axis=0)
        scale = 1.4826 * np.median(np.abs(X - center), axis=0) + 1e-9
        Z = (X - center) / scale
        iso = IsolationForest(n_estimators=200, random_state=seed, n_jobs=1).fit(Z)
        iso_cut = float(np.quantile(-iso.score_samples(Z), 1 - CLEAN_RATE))
        mcd, mcd_cut = None, float("inf")
        if len(Z) > 3 * Z.shape[1] and Z.shape[1] <= 50:
            mcd = MinCovDet(random_state=seed).fit(Z)
            mcd_cut = float(np.quantile(mcd.mahalanobis(Z), 1 - CLEAN_RATE))
        ae = _fit_autoencoder(Z, seed)
        ae_cut = float(np.quantile(_ae_scores(ae, Z), 1 - CLEAN_RATE))
        explicit = dict(ranges or {})
        # Default physical ranges apply only to columns in physical units: if the registered clean data already
        # leave a default range (e.g. z-scored columns), that range is not meaningful for this dataset.
        rng = {c: explicit[c] for c in cols if c in explicit}
        for c in cols:
            if c not in rng and c in DEFAULT_RANGES:
                lo, hi = DEFAULT_RANGES[c]
                if float(num[c].min()) >= lo and float(num[c].max()) <= hi:
                    rng[c] = (lo, hi)
        b = cls(cols, center, scale, {c: num[c].dropna().to_numpy(float) for c in cols}, rng,
                iso, iso_cut, mcd, mcd_cut, ae, ae_cut, len(df), seed)
        if meta is not None:
            for col in meta.columns:
                if meta[col].nunique() == 2:
                    agree = _knn_agreement(Z, pd.factorize(meta[col])[0])
                    if agree.mean() >= 0.65:
                        b.label_rates[col] = float(np.mean(agree <= 0.2))
        b._digest = hashlib.sha256(np.concatenate([center, scale, [iso_cut, ae_cut, len(df)]]).tobytes()).hexdigest()
        return b

    def digest(self) -> str:
        """Short fingerprint to store in the ledger when the baseline is registered."""
        return self._digest

    def summary(self) -> dict:
        return {"n_rows": self.n_rows, "columns": self.columns, "digest": self._digest,
                "cutoffs": {"isolation_forest": self.iso_cut, "mcd": self.mcd_cut, "autoencoder": self.ae_cut}}


def _legacy_baseline(baseline: dict, df: pd.DataFrame) -> Optional["Baseline"]:
    """Support the older dict form ``{"X_matrix": ..., col: {"sample": ...}}``."""
    if "X_matrix" in baseline:
        Xb = np.asarray(baseline["X_matrix"], float)
        cols = list(df.select_dtypes(include=[np.number]).columns)[: Xb.shape[1]]
        frame = pd.DataFrame(Xb, columns=cols[: Xb.shape[1]] if len(cols) >= Xb.shape[1] else range(Xb.shape[1]))
        return Baseline.from_frame(frame)
    return None


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #
def _flag(report: SecurityReport, name: str, scores: np.ndarray, cut: float, label: str) -> np.ndarray:
    flagged = scores > cut
    n_flag, n = int(flagged.sum()), len(scores)
    limit = _binom_cutoff(n)
    if n_flag > limit:
        report.add_check(name, "WARN", float(n_flag), f"{n_flag}/{n} rows above the clean 99th-percentile {label} cutoff (clean expectation {CLEAN_RATE * n:.1f}, alarm above {limit})",
                         {"flagged": n_flag, "limit": limit})
    else:
        report.add_check(name, "PASS", 0.0, f"{n_flag}/{n} rows above the {label} cutoff (within clean expectation)",
                         {"flagged": n_flag, "limit": limit})
    return flagged


def scan_dataset(df_or_expr: pd.DataFrame, meta: Optional[pd.DataFrame] = None,
                 baseline: "Baseline | Dict[str, Any] | None" = None,
                 ranges: Optional[Dict[str, tuple]] = None) -> SecurityReport:
    """Run the ensemble. See the module docstring for the calibration and blocking policy."""
    df = df_or_expr
    report = SecurityReport()
    n = len(df)
    report.suspicion_scores = np.zeros(n)

    base: Optional[Baseline] = None
    drift_samples: Dict[str, np.ndarray] = {}
    if isinstance(baseline, Baseline):
        base = baseline
        drift_samples = baseline.samples
    elif isinstance(baseline, dict):
        base = _legacy_baseline(baseline, df)
        drift_samples = {k: np.asarray(v["sample"], float) for k, v in baseline.items()
                         if isinstance(v, dict) and "sample" in v}

    # 1. Physical range (blocking)
    # ranges=None -> baseline's ranges (or the defaults); ranges={} -> no range check (e.g. z-scored data)
    eff_ranges = dict(ranges) if ranges is not None else (dict(base.ranges) if base is not None else _plausible_defaults(df))
    if eff_ranges:
        bad = 0
        worst = {}
        for col, (lo, hi) in eff_ranges.items():
            if col in df.columns:
                v = df[col].dropna()
                nbad = int(((v < lo) | (v > hi)).sum())
                if nbad:
                    worst[col] = nbad
                    bad += nbad
                    idx = df.index.get_indexer(v.index[(v < lo) | (v > hi)])
                    report.suspicion_scores[idx[idx >= 0]] += 10.0
        if bad:
            report.add_check("physical_range", "FAIL", float(bad), f"{bad} values outside physical limits in {sorted(worst)}", worst)
        else:
            report.add_check("physical_range", "PASS", 0.0, "All values within physical ranges")

    # 2. Duplicates (advisory)
    num = df.select_dtypes(include=[np.number])
    if len(num.columns):
        dup = int(num.round(10).duplicated(keep=False).sum())
        if dup:
            report.add_check("duplicates", "WARN", float(dup), f"{dup} rows duplicate another row exactly")
        else:
            report.add_check("duplicates", "PASS", 0.0, "No exact duplicate rows")

    # 3. Multivariate outlier ensemble (advisory)
    try:
        cols = base.columns if base is not None else list(num.loc[:, num.nunique() > 1].columns)
        X = num[cols].fillna(num[cols].median()).to_numpy(float)
        if base is None:
            base_local = None
            center = np.median(X, axis=0)
            scale = 1.4826 * np.median(np.abs(X - center), axis=0) + 1e-9
        else:
            base_local = base
            center, scale = base.center, base.scale
        Z = (X - center) / scale

        if base_local is not None:
            iso_s = -base_local.iso.score_samples(Z)
            iso_cut = base_local.iso_cut
        else:
            iso = IsolationForest(n_estimators=200, random_state=0, n_jobs=1).fit(Z)
            iso_s = -iso.score_samples(Z)
            iso_cut = float(np.median(iso_s) + 5 * 1.4826 * np.median(np.abs(iso_s - np.median(iso_s))))
        f1 = _flag(report, "isolation_forest", iso_s, iso_cut, "IsolationForest")

        if base_local is not None and base_local.mcd is not None:
            d2 = base_local.mcd.mahalanobis(Z)
            mcd_cut = base_local.mcd_cut
        elif Z.shape[0] >= max(40, 5 * Z.shape[1]) and Z.shape[1] <= 50:   # a robust covariance needs enough rows
            m = MinCovDet(random_state=0).fit(Z)
            d2 = m.mahalanobis(Z)
            p = Z.shape[1]
            mcd_cut = float(stats.chi2.ppf(0.999, p) * np.median(d2) / stats.chi2.ppf(0.5, p))
        else:
            d2, mcd_cut = np.zeros(n), np.inf
        f2 = _flag(report, "mcd", d2, mcd_cut, "robust-Mahalanobis")

        if base_local is not None:
            ae_s = _ae_scores(base_local.ae, Z)
            ae_cut = base_local.ae_cut
        else:
            net = _fit_autoencoder(Z, 0)
            ae_s = _ae_scores(net, Z)
            ae_cut = float(np.median(ae_s) + 5 * 1.4826 * np.median(np.abs(ae_s - np.median(ae_s))))
        f3 = _flag(report, "autoencoder", ae_s, ae_cut, "autoencoder reconstruction")

        report.suspicion_scores += (iso_s / (iso_cut + 1e-12) + np.nan_to_num(d2 / (mcd_cut + 1e-12))
                                    + ae_s / (ae_cut + 1e-12)) / 3.0
        del f1, f2, f3
    except Exception as exc:  # pragma: no cover - defensive; reported, never hidden
        for nm in ("isolation_forest", "mcd", "autoencoder"):
            report.add_check(nm, "WARN", 1.0, f"check could not run: {exc}")

    # 4. Distribution drift vs baseline (advisory)
    if drift_samples:
        cols, pvals, psis = [], [], []
        for col, ref in drift_samples.items():
            if col in df.columns:
                v = df[col].dropna().to_numpy(float)
                if len(v) > 5 and len(ref) > 5:
                    cols.append(col)
                    pvals.append(float(stats.ks_2samp(v, ref).pvalue))
                    psis.append(calculate_psi(ref, v))
        if cols:
            q = bh_fdr(np.array(pvals))
            drifted = [c for c, qq, ps in zip(cols, q, psis) if qq < 0.001 and ps > 0.2]
            if drifted:
                report.add_check("distribution_drift", "WARN", float(len(drifted)),
                                 f"{len(drifted)} feature(s) drifted vs baseline (KS q<0.001 and PSI>0.2): {drifted}",
                                 {"features": drifted})
            else:
                report.add_check("distribution_drift", "PASS", 0.0, "No significant distribution drift vs baseline")

    # 5. Label-flip / metadata consistency (advisory)
    if meta is not None and len(num.columns):
        try:
            if base is not None:
                Xl = num[base.columns].fillna(num[base.columns].median()).to_numpy(float)
                Zs = (Xl - base.center) / base.scale
            else:
                Xl = num.fillna(num.median()).to_numpy(float)
                Zs = (Xl - np.median(Xl, 0)) / (1.4826 * np.median(np.abs(Xl - np.median(Xl, 0)), 0) + 1e-9)
            flips, informative, limit = 0, False, _binom_cutoff(n)
            for col in meta.columns:
                if meta[col].nunique() == 2:
                    agree = _knn_agreement(Zs, pd.factorize(meta[col])[0])
                    if agree.mean() < 0.65:
                        continue
                    informative = True
                    bad = agree <= 0.2
                    report.suspicion_scores[bad] += 5.0
                    flips += int(bad.sum())
                    if base is not None and col in base.label_rates:
                        limit = max(limit, _binom_cutoff(n, max(base.label_rates[col], CLEAN_RATE)))
            if not informative:
                report.add_check("label_flip", "PASS", 0.0,
                                 "Labels carry no separable structure in feature space; this check cannot be informative here")
            elif flips > limit:
                report.add_check("label_flip", "WARN", float(flips), f"{flips} samples disagree with nearly all of their nearest neighbours")
            else:
                report.add_check("label_flip", "PASS", 0.0, "Labels consistent with feature space")
        except Exception as exc:  # pragma: no cover
            report.add_check("label_flip", "WARN", 1.0, f"check could not run: {exc}")

    # 6. Temporal sanity (blocking)
    date_cols = [c for c in df.columns if "date" in str(c).lower() or "time" in str(c).lower()]
    if date_cols:
        dc = date_cols[0]
        try:
            d = pd.to_datetime(df[dc])
            mono = (df.assign(_d=d).groupby("city")["_d"].apply(lambda x: x.is_monotonic_increasing).all()
                    if "city" in df.columns else d.is_monotonic_increasing)
            if mono:
                report.add_check("temporal_sanity", "PASS", 0.0, "Timestamps strictly monotonic")
            else:
                report.add_check("temporal_sanity", "FAIL", 1.0, f"Timestamps in {dc} are not monotonic")
        except Exception as exc:  # pragma: no cover
            report.add_check("temporal_sanity", "WARN", 1.0, f"check could not run: {exc}")

    return report
