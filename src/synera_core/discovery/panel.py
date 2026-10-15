"""Panel-aware interaction discovery for continuous environmental stressors.

Model ladder for a stressor pair (a, b), fitted on a city x day panel:

    M0  y ~ city FE + sin/cos(day-of-year) + linear(all other stressors)
            + spline(a) + spline(b)                              (additive smooth)
    M1  M0 + a:b                                                 (bilinear interaction)
    M2  M1 + spline(a) (x) spline(b) tensor columns              (full surface)

The *joint* interaction test is M0 -> M2. Classification uses two sub-tests:
M0 -> M1 (bilinear) and M1 -> M2 (non-linear surface).

Three p-values are produced for every block of added terms:

* ``p_naive``  - classical F-test. Assumes independent errors, which a daily panel
  violates; reported only to show the size of the inflation.
* ``p_hac``    - Wald test with a per-city Newey-West (Bartlett) covariance.
* ``p_boot``   - block-bootstrap calibrated F-test. Residuals of the null model
  (M0) are resampled in moving blocks inside each city (Freedman-Lane style),
  the F statistic is recomputed for every resample, and the observed F is
  rescaled by the bootstrap-to-nominal ratio of medians before the F reference
  distribution is applied. This is a calibration device, not an exact test.

Everything operates on one dataframe sorted by (city, date); the helpers assume
that ordering and never silently re-sort.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import linalg, stats
from scipy.interpolate import BSpline

from synera_core.validation.multitest import bh_fdr

SPLINE_DEGREE = 3
SPLINE_INTERIOR_KNOTS = 1  # -> 5 B-spline columns per stressor (rank handled by QR)


# --------------------------------------------------------------------------- #
# Basis construction
# --------------------------------------------------------------------------- #
@dataclass
class SplineBasis:
    """Cubic B-spline basis with fixed knots so it can be re-evaluated on a grid."""

    knots: np.ndarray
    lo: float
    hi: float

    @classmethod
    def fit(cls, x: np.ndarray) -> "SplineBasis":
        lo, hi = float(np.min(x)), float(np.max(x))
        interior = np.quantile(x, np.linspace(0, 1, SPLINE_INTERIOR_KNOTS + 2)[1:-1])
        knots = np.concatenate([[lo] * (SPLINE_DEGREE + 1), interior, [hi] * (SPLINE_DEGREE + 1)])
        return cls(knots=knots, lo=lo, hi=hi)

    def transform(self, x: np.ndarray) -> np.ndarray:
        xc = np.clip(np.asarray(x, float), self.lo, self.hi)
        return BSpline.design_matrix(xc, self.knots, SPLINE_DEGREE).toarray()


def _season_columns(dates: pd.Series) -> np.ndarray:
    doy = pd.to_datetime(dates).dt.dayofyear.to_numpy(float)
    return np.column_stack([np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)])


@dataclass
class PanelData:
    """Arrays shared by every pair test of one dataset."""

    y: np.ndarray
    stressors: dict[str, np.ndarray]
    city_codes: np.ndarray
    city_slices: list[slice]
    city_names: list[str]
    season: np.ndarray
    dates: np.ndarray
    n: int = field(init=False)

    def __post_init__(self) -> None:
        self.n = len(self.y)


def make_panel(df: pd.DataFrame, y_col: str, stressors: Sequence[str],
               city_col: str = "city", date_col: str = "date") -> PanelData:
    """Validate ordering and convert a dataframe into :class:`PanelData`.

    Raises ``ValueError`` if rows are not sorted by (city, date) or contain NaN.
    """
    cols = [y_col, *stressors]
    if df[cols].isna().any().any():
        raise ValueError("make_panel: NaN present; drop incomplete rows explicitly before calling")
    codes, names = pd.factorize(df[city_col], sort=False)
    d = pd.to_datetime(df[date_col]).to_numpy()
    order_ok = True
    slices: list[slice] = []
    start = 0
    for i in range(1, len(df) + 1):
        if i == len(df) or codes[i] != codes[start]:
            seg = d[start:i]
            order_ok &= bool(np.all(np.diff(seg).astype("timedelta64[D]").astype(int) > 0))
            slices.append(slice(start, i))
            start = i
    if len(slices) != len(names) or not order_ok:
        raise ValueError("make_panel: rows must be contiguous per city and strictly increasing in date")
    return PanelData(
        y=df[y_col].to_numpy(float),
        stressors={s: df[s].to_numpy(float) for s in stressors},
        city_codes=codes.astype(int),
        city_slices=slices,
        city_names=[str(c) for c in names],
        season=_season_columns(df[date_col]),
        dates=d,
    )


def _base_matrix(panel: PanelData, a: str, b: str, extra: np.ndarray | None,
                 bases: dict[str, SplineBasis]) -> np.ndarray:
    n = panel.n
    cols = [np.ones((n, 1))]
    k = len(panel.city_names)
    if k > 1:
        d = np.zeros((n, k - 1))
        for j in range(1, k):
            d[panel.city_codes == j, j - 1] = 1.0
        cols.append(d)
    cols.append(panel.season)
    for name, x in panel.stressors.items():
        if name not in (a, b):
            cols.append(x[:, None])
    cols.append(bases[a].transform(panel.stressors[a]))
    cols.append(bases[b].transform(panel.stressors[b]))
    if extra is not None and extra.size:
        cols.append(extra)
    return np.column_stack(cols)


def _extras_matrix(panel: PanelData, a: str, b: str, bases: dict[str, SplineBasis]) -> tuple[np.ndarray, int]:
    """Return ``[a*b | tensor columns]`` and the number of leading bilinear columns (1)."""
    xa, xb = panel.stressors[a], panel.stressors[b]
    Ba, Bb = bases[a].transform(xa), bases[b].transform(xb)
    tensor = np.einsum("ni,nj->nij", Ba, Bb).reshape(panel.n, -1)
    return np.column_stack([xa * xb, tensor]), 1


def _rank_basis(X: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    q, r, _ = linalg.qr(X, mode="economic", pivoting=True)
    diag = np.abs(np.diag(r))
    rank = int(np.sum(diag > tol * diag[0]))
    return q[:, :rank]


def _orthogonal_extras(Q0: np.ndarray, E: np.ndarray, tol: float = 1e-8) -> np.ndarray:
    """Orthonormal basis (n x r) of span(E) after projecting out span(Q0)."""
    Et = E - Q0 @ (Q0.T @ E)
    u, s, _ = np.linalg.svd(Et, full_matrices=False)
    r = int(np.sum(s > tol * max(s[0], 1e-12)))
    return u[:, :r]


# --------------------------------------------------------------------------- #
# Block bootstrap helpers
# --------------------------------------------------------------------------- #
def auto_block_length(resid: np.ndarray, city_slices: list[slice], max_len: int = 30) -> int:
    """Block length from residual autocorrelation: twice the lag at which the pooled ACF
    first falls inside the +-2/sqrt(n) band (minimum 5)."""
    lags = 40
    acf = np.zeros(lags)
    for sl in city_slices:
        r = resid[sl] - resid[sl].mean()
        denom = float(r @ r) + 1e-12
        for k in range(1, lags + 1):
            acf[k - 1] += float(r[:-k] @ r[k:]) / denom
    acf /= len(city_slices)
    band = 2.0 / np.sqrt(np.mean([s.stop - s.start for s in city_slices]))
    below = np.where(np.abs(acf) < band)[0]
    first = int(below[0]) + 1 if len(below) else lags
    return int(min(max_len, max(5, 2 * first)))


def block_indices(city_slices: list[slice], block_len: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap row indices, shape (n, n_boot), resampling inside each city."""
    parts = []
    for sl in city_slices:
        n_c = sl.stop - sl.start
        L = min(block_len, n_c)
        n_blocks = int(np.ceil(n_c / L))
        starts = rng.integers(0, n_c - L + 1, size=(n_blocks, n_boot))
        idx = starts[:, None, :] + np.arange(L)[None, :, None]
        parts.append(idx.reshape(n_blocks * L, n_boot)[:n_c] + sl.start)
    return np.vstack(parts)


# --------------------------------------------------------------------------- #
# Block test
# --------------------------------------------------------------------------- #
@dataclass
class BlockTest:
    """Result of testing a block of added regressors against a base design."""

    r: int
    df_res: int
    F: float
    p_naive: float
    p_hac: float
    p_boot: float
    lambda_boot: float
    beta: np.ndarray
    U: np.ndarray

    def to_dict(self) -> dict:
        return {
            "r": self.r, "df_res": self.df_res, "F": float(self.F),
            "p_naive": float(self.p_naive), "p_hac": float(self.p_hac),
            "p_boot": float(self.p_boot), "lambda_boot": float(self.lambda_boot),
        }


def _hac_wald(U: np.ndarray, e: np.ndarray, beta: np.ndarray, city_slices: list[slice],
              n_params: int, lags: int | None = None) -> float:
    r = U.shape[1]
    S = U * e[:, None]
    L = lags or max(1, int(np.floor(4 * (np.mean([s.stop - s.start for s in city_slices]) / 100.0) ** (2 / 9))))
    omega = np.zeros((r, r))
    for sl in city_slices:
        s = S[sl]
        omega += s.T @ s
        for lag in range(1, L + 1):
            w = 1.0 - lag / (L + 1.0)
            g = s[lag:].T @ s[:-lag]
            omega += w * (g + g.T)
    omega *= U.shape[0] / max(U.shape[0] - n_params, 1)
    try:
        W = float(beta @ np.linalg.solve(omega, beta))
    except np.linalg.LinAlgError:
        return float("nan")
    return float(stats.chi2.sf(W, r))


def test_block(panel: PanelData, X0: np.ndarray, E: np.ndarray, boot_idx: np.ndarray | None,
               y: np.ndarray | None = None, hac_lags: int | None = None) -> BlockTest:
    """Test the extra columns ``E`` against base design ``X0`` (see module docstring)."""
    y = panel.y if y is None else y
    n = panel.n
    Q0 = _rank_basis(X0)
    p0 = Q0.shape[1]
    U = _orthogonal_extras(Q0, E)
    r = U.shape[1]
    if r == 0:
        return BlockTest(0, n - p0, np.nan, np.nan, np.nan, np.nan, np.nan, np.zeros(0), U)
    resid0 = y - Q0 @ (Q0.T @ y)
    beta = U.T @ y
    e1 = resid0 - U @ beta
    df_res = n - p0 - r
    rss1 = float(e1 @ e1)
    F = float((beta @ beta / r) / (rss1 / df_res))
    p_naive = float(stats.f.sf(F, r, df_res))
    p_hac = _hac_wald(U, e1, beta, panel.city_slices, p0 + r, hac_lags)

    p_boot, lam = float("nan"), float("nan")
    if boot_idx is not None:
        eps = resid0[boot_idx]                       # n x B resampled null residuals
        rss0_b = np.einsum("ij,ij->j", eps, eps) - np.einsum("ij,ij->j", Q0.T @ eps, Q0.T @ eps)
        bb = U.T @ eps
        rss1_b = rss0_b - np.einsum("ij,ij->j", bb, bb)
        Fb = (np.einsum("ij,ij->j", bb, bb) / r) / (np.maximum(rss1_b, 1e-12) / df_res)
        lam = float(np.median(Fb) / stats.f.ppf(0.5, r, df_res))
        lam = max(lam, 1e-3)
        # Moment-matched gamma reference for the bootstrap null distribution of F: keeps the heavier
        # tail that a weighted sum of chi-squares has when errors are autocorrelated.
        m_b, v_b = float(np.mean(Fb)), float(np.var(Fb, ddof=1))
        shape, scale = m_b ** 2 / v_b, v_b / m_b
        p_boot = float(stats.gamma.sf(F, shape, scale=scale))
    return BlockTest(r, df_res, F, p_naive, p_hac, p_boot, lam, beta, U)


# --------------------------------------------------------------------------- #
# Pair-level results
# --------------------------------------------------------------------------- #
@dataclass
class PairResult:
    a: str
    b: str
    joint: BlockTest
    bilinear: BlockTest | None = None
    nonlinear: BlockTest | None = None
    type: str = "none"
    effect_size: float = float("nan")
    b_AB_std: float = float("nan")
    ci_low: float = float("nan")
    ci_high: float = float("nan")
    eff_ci_low: float = float("nan")
    eff_ci_high: float = float("nan")
    surface: dict | None = None
    conditional_p: float | None = None
    q: dict = field(default_factory=dict)
    passes_effect: bool = False
    ci_clears_gate: bool = False

    @property
    def pair(self) -> tuple[str, str]:
        return (self.a, self.b)


class PanelDiscovery:
    """Run the full discovery stack over all stressor pairs of one panel dataset."""

    def __init__(self, df: pd.DataFrame, y_col: str, stressors: Sequence[str], *,
                 alpha: float = 0.05, n_boot: int = 299, effect_gate: float = 0.05,
                 seed: int = 0, block_len: int | None = None, n_ci: int = 200) -> None:
        self.stressors = list(stressors)
        self.panel = make_panel(df, y_col, self.stressors)
        self.alpha = alpha
        self.effect_gate = effect_gate
        self.n_boot = n_boot
        self.n_ci = n_ci
        self.rng = np.random.default_rng(seed)
        self.bases = {s: SplineBasis.fit(self.panel.stressors[s]) for s in self.stressors}
        self.pairs = [(a, b) for i, a in enumerate(self.stressors) for b in self.stressors[i + 1:]]
        # Block length from the residuals of the main-effects-only model.
        main = _base_matrix(self.panel, self.stressors[0], self.stressors[1], None, self.bases)
        Q = _rank_basis(main)
        res = self.panel.y - Q @ (Q.T @ self.panel.y)
        self.block_len = block_len or auto_block_length(res, self.panel.city_slices)
        self.boot_idx = block_indices(self.panel.city_slices, self.block_len, n_boot, self.rng)

    # -- single pair ---------------------------------------------------------
    def _test_pair(self, a: str, b: str, accepted: list[tuple[str, str]] | None = None) -> PairResult:
        extra = None
        if accepted:
            mats = [_extras_matrix(self.panel, x, z, self.bases)[0] for x, z in accepted]
            extra = np.column_stack(mats)
        X0 = _base_matrix(self.panel, a, b, extra, self.bases)
        E, _ = _extras_matrix(self.panel, a, b, self.bases)
        joint = test_block(self.panel, X0, E, self.boot_idx, hac_lags=self.block_len)
        return PairResult(a, b, joint)

    def screen(self) -> list[PairResult]:
        """Marginal screen of every pair; adds ``q`` via BH over all pairs."""
        return [self._test_pair(a, b) for a, b in self.pairs]

    # -- characterisation of accepted pairs ----------------------------------
    def characterise(self, res: PairResult, accepted_before: list[tuple[str, str]] | None = None,
                     n_ci: int | None = None) -> PairResult:
        n_ci = n_ci or self.n_ci
        a, b = res.a, res.b
        extra = None
        if accepted_before:
            extra = np.column_stack([_extras_matrix(self.panel, x, z, self.bases)[0] for x, z in accepted_before])
        X0 = _base_matrix(self.panel, a, b, extra, self.bases)
        E, nbil = _extras_matrix(self.panel, a, b, self.bases)
        res.bilinear = test_block(self.panel, X0, E[:, :nbil], self.boot_idx, hac_lags=self.block_len)
        X1 = np.column_stack([X0, E[:, :nbil]])
        res.nonlinear = test_block(self.panel, X1, E[:, nbil:], self.boot_idx, hac_lags=self.block_len)

        p_nl = res.nonlinear.p_boot
        p_bl = res.bilinear.p_boot
        if np.isfinite(p_nl) and p_nl < self.alpha:
            res.type = "NONLINEAR"
        elif np.isfinite(p_bl) and p_bl < self.alpha:
            res.type = "SYNERGISTIC" if self._direction(X0, E, a, b, accepted_before) > 0 else "ANTAGONISTIC"
        else:
            # joint signal without a significant sub-component: surface not separable
            res.type = "NONLINEAR" if (res.nonlinear.F or 0) > (res.bilinear.F or 0) else (
                "SYNERGISTIC" if self._direction(X0, E, a, b, accepted_before) > 0 else "ANTAGONISTIC")

        sd_y = float(np.std(self.panel.y))
        res.effect_size = float(np.std(res.joint.U @ res.joint.beta) / sd_y)
        res.surface = self._surface(X0, E, a, b, accepted_before)
        boot = self._bootstrap_effect(X0, E, sd_y, n_ci)
        res.b_AB_std, res.ci_low, res.ci_high = boot["b"], boot["b_lo"], boot["b_hi"]
        res.eff_ci_low, res.eff_ci_high = boot["eff_lo"], boot["eff_hi"]
        res.passes_effect = bool(res.effect_size >= self.effect_gate)
        # The effect must stay above the pre-specified minimal effect across block-bootstrap resamples.
        res.ci_clears_gate = bool(res.eff_ci_low >= self.effect_gate)
        return res

    def _direction(self, X0: np.ndarray, E: np.ndarray, a: str, b: str,
                   accepted: list[tuple[str, str]] | None = None) -> float:
        """+1 if the bilinear coefficient amplifies the additive effect at the upper quartiles."""
        X1 = np.column_stack([X0, E[:, :1]])
        beta = np.linalg.lstsq(X1, self.panel.y, rcond=None)[0]
        c_ab = beta[-1]
        xa, xb = self.panel.stressors[a], self.panel.stressors[b]
        qa, qb = np.quantile(xa, 0.75), np.quantile(xb, 0.75)
        # additive effect of raising a and b to Q3 from the mean, using fitted M1
        def pred(va, vb):
            Xg = self._grid_design(X0, a, b, np.array([va]), np.array([vb]), with_bilinear=True, accepted=accepted)
            return float((Xg @ beta)[0])
        base = pred(float(xa.mean()), float(xb.mean()))
        main = (pred(qa, float(xb.mean())) - base) + (pred(float(xa.mean()), qb) - base)
        return float(np.sign(main * c_ab)) or 1.0

    def _grid_design(self, X0: np.ndarray, a: str, b: str, ga: np.ndarray, gb: np.ndarray,
                     with_bilinear: bool = False, with_tensor: bool = False,
                     accepted: list[tuple[str, str]] | None = None) -> np.ndarray:
        """Design rows for given (a, b) values; every other covariate at its column mean."""
        m = len(ga)
        base_means = X0.mean(axis=0)
        n_base = X0.shape[1]
        # Locate the a/b spline blocks: they are the last blocks before `extra`; rebuild by position.
        k = len(self.panel.city_names)
        offset = 1 + (k - 1) + 2 + (len(self.stressors) - 2)
        Ba, Bb = self.bases[a].transform(ga), self.bases[b].transform(gb)
        wa, wb = Ba.shape[1], Bb.shape[1]
        rows = np.tile(base_means, (m, 1))
        rows[:, offset:offset + wa] = Ba
        rows[:, offset + wa:offset + wa + wb] = Bb
        if offset + wa + wb > n_base:
            raise RuntimeError("grid design misaligned")
        if accepted:
            # Columns of already-accepted interaction surfaces depend on a and/or b: recompute them
            # on the grid, holding every other stressor at its (zero) mean.
            pos = offset + wa + wb
            for x, z in accepted:
                vx = ga if x == a else gb if x == b else np.full(m, float(self.panel.stressors[x].mean()))
                vz = ga if z == a else gb if z == b else np.full(m, float(self.panel.stressors[z].mean()))
                Bx, Bz = self.bases[x].transform(vx), self.bases[z].transform(vz)
                block = np.column_stack([vx * vz, np.einsum("ni,nj->nij", Bx, Bz).reshape(m, -1)])
                rows[:, pos:pos + block.shape[1]] = block
                pos += block.shape[1]
        extras = []
        if with_bilinear:
            extras.append((ga * gb)[:, None])
        if with_tensor:
            extras.append(np.einsum("ni,nj->nij", Ba, Bb).reshape(m, -1))
        return np.column_stack([rows, *extras]) if extras else rows

    def _surface(self, X0: np.ndarray, E: np.ndarray, a: str, b: str,
                 accepted: list[tuple[str, str]] | None = None, size: int = 30) -> dict:
        y = self.panel.y
        X2 = np.column_stack([X0, E])
        beta2 = np.linalg.lstsq(X2, y, rcond=None)[0]
        beta0 = np.linalg.lstsq(X0, y, rcond=None)[0]
        xa, xb = self.panel.stressors[a], self.panel.stressors[b]
        ga = np.linspace(np.quantile(xa, 0.02), np.quantile(xa, 0.98), size)
        gb = np.linspace(np.quantile(xb, 0.02), np.quantile(xb, 0.98), size)
        AA, BB = np.meshgrid(ga, gb)
        fa, fb = AA.ravel(), BB.ravel()
        Xg0 = self._grid_design(X0, a, b, fa, fb, accepted=accepted)
        Xg2 = self._grid_design(X0, a, b, fa, fb, with_bilinear=True, with_tensor=True, accepted=accepted)
        z0 = (Xg0 @ beta0).reshape(size, size)
        z2 = (Xg2 @ beta2).reshape(size, size)
        sd = float(np.std(y))
        return {
            "a": a, "b": b,
            "grid_a": ga.tolist(), "grid_b": gb.tolist(),
            "z_additive": (z0 / sd).tolist(), "z_full": (z2 / sd).tolist(),
            "z_gap": ((z2 - z0) / sd).tolist(),
            "units": "outcome SD (standardised stressors, per-city z-scores)",
        }

    def _bootstrap_effect(self, X0: np.ndarray, E: np.ndarray, sd_y: float, n_ci: int) -> dict:
        """Moving-block *case* bootstrap (rows resampled in blocks inside each city).

        Returns the signed bilinear coefficient and the interaction-surface effect size, both in
        outcome-SD units, with 95% percentile intervals.
        """
        y = self.panel.y
        X1 = np.column_stack([X0, E[:, :1]])
        X2 = np.column_stack([X0, E])
        b_hat = float(np.linalg.lstsq(X1, y, rcond=None)[0][-1] / sd_y)
        idx = block_indices(self.panel.city_slices, self.block_len, n_ci, self.rng)
        b_boot = np.empty(n_ci)
        e_boot = np.empty(n_ci)
        for j in range(n_ci):
            ii = idx[:, j]
            yj = y[ii]
            b_boot[j] = np.linalg.lstsq(X1[ii], yj, rcond=None)[0][-1] / sd_y
            b2 = np.linalg.lstsq(X2[ii], yj, rcond=None)[0]
            b0 = np.linalg.lstsq(X0[ii], yj, rcond=None)[0]
            e_boot[j] = np.std(X2 @ b2 - X0 @ b0) / sd_y
        b_lo, b_hi = np.percentile(b_boot, [2.5, 97.5])
        e_lo, e_hi = np.percentile(e_boot, [2.5, 97.5])
        return {"b": b_hat, "b_lo": float(b_lo), "b_hi": float(b_hi), "eff_lo": float(e_lo), "eff_hi": float(e_hi)}

    # -- full run --------------------------------------------------------------
    def _bh_scaled(self, p: np.ndarray, m_total: int) -> np.ndarray:
        """BH q-values over ``p`` with the denominator fixed at ``m_total`` (conservative)."""
        srt = np.argsort(p)
        adj = np.minimum.accumulate((p[srt] * m_total / np.arange(1, len(p) + 1))[::-1])[::-1]
        q = np.empty(len(p))
        q[srt] = np.clip(adj, 0, 1)
        return q

    def holdout_check(self, a: str, b: str, others: list[tuple[str, str]] | None = None) -> dict:
        """Joint test p-value and interaction direction of pair (a, b) on this dataset, given ``others`` already in the model.

        Used for internal replication: build a :class:`PanelDiscovery` on a subset of cities and call this per pair.
        """
        extra = np.column_stack([_extras_matrix(self.panel, x, z, self.bases)[0] for x, z in others]) if others else None
        X0 = _base_matrix(self.panel, a, b, extra, self.bases)
        E, _ = _extras_matrix(self.panel, a, b, self.bases)
        joint = test_block(self.panel, X0, E, self.boot_idx, hac_lags=self.block_len)
        return {"p_boot": float(joint.p_boot), "direction": int(self._direction(X0, E, a, b, others or None))}

    def run(self, p_column: str = "p_boot", progress=None, on_stage=None) -> dict:
        """Screen -> BH -> forward selection -> backward elimination -> characterisation.

        1. Marginal screen of every pair (``screen``), BH over all pairs.
        2. Forward selection: accept the most significant pair, re-test the other candidates
           *conditional on the accepted surfaces* (this removes proxies of an accepted pair).
        3. Backward elimination: re-test every accepted pair given all the others and drop
           pairs that no longer pass BH (scaled to the total number of pairs tested).
        4. Each surviving pair is characterised given all the other survivors.

        Returns a dict with the marginal screen, the final ``accepted`` list and stage counts.
        """
        screen = self.screen()
        key = np.array([getattr(r.joint, p_column) for r in screen])
        q = {col: bh_fdr(np.array([getattr(r.joint, col) for r in screen])) for col in ("p_naive", "p_hac", "p_boot")}
        for i, r in enumerate(screen):
            r.q = {col: float(q[col][i]) for col in q}
        m_total = len(screen)
        remaining = [int(i) for i in np.argsort(key) if q[p_column][i] < self.alpha and np.isfinite(key[i])]
        n_marginal = len(remaining)
        if on_stage:
            on_stage("screen", {"n_pairs": m_total, "n_raw": int(np.sum(key < self.alpha)), "n_marginal_bh": n_marginal})

        selected: list[int] = []
        while remaining:
            top = remaining.pop(0)
            screen[top].conditional_p = float(key[top])
            selected.append(top)
            if not remaining:
                break
            acc = [screen[i].pair for i in selected]
            cond = np.array([getattr(self._test_pair(screen[i].a, screen[i].b, accepted=acc).joint, p_column)
                             for i in remaining])
            qc = self._bh_scaled(cond, m_total)
            keep = sorted((c, i) for i, c, qq in zip(remaining, cond, qc) if qq < self.alpha and np.isfinite(c))
            remaining = [i for _, i in keep]
        n_forward = len(selected)
        if on_stage:
            on_stage("forward", {"n": n_forward})

        # Backward elimination against the final model.
        while len(selected) > 1:
            ps = []
            for i in selected:
                others = [screen[j].pair for j in selected if j != i]
                ps.append(getattr(self._test_pair(screen[i].a, screen[i].b, accepted=others).joint, p_column))
            ps_arr = np.array(ps)
            qb = self._bh_scaled(ps_arr, m_total)
            worst = int(np.nanargmax(ps_arr))
            if np.isfinite(ps_arr[worst]) and qb[worst] < self.alpha:
                break  # every remaining pair is significant given all the others
            selected.pop(worst)
        n_backward = len(selected)
        if on_stage:
            on_stage("backward", {"n": n_backward})

        accepted: list[PairResult] = []
        for i in selected:
            res = screen[i]
            others = [screen[j].pair for j in selected if j != i]
            if others:
                res.conditional_p = float(getattr(self._test_pair(res.a, res.b, accepted=others).joint, p_column))
            self.characterise(res, accepted_before=others or None)
            accepted.append(res)
            if progress:
                progress(len(accepted), res)
        return {
            "screen": screen,
            "q": q,
            "accepted": accepted,
            "stage_counts": {"marginal_bh": n_marginal, "after_forward": n_forward, "after_backward": n_backward},
            "block_len": self.block_len,
            "n_rows": self.panel.n,
            "n_pairs": m_total,
        }



