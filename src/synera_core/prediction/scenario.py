"""Scenario model: what a combination of weather and air-pollution conditions does to weekly deaths in a US state.

Learned from the REAL panels (CDC weekly deaths x EPA monitors x ERA5/NASA weather; scripts/build_health_panel.py).

    outcome  = % excess deaths versus the state's own expected level for that week, minus the national figure that week
               (so nationwide flu waves and weather cannot pose as the effect of a local stressor)
    inputs   = each stressor's *anomaly*: the chosen level minus the state's normal for that week, in units of the state's own
               usual deviation ("+2" = two usual deviations hotter / dirtier than normal there), also compared with the other
               states in the same week when fitting
    terms    = 10 linear + heat curvature (squared) + heat x time of year (heat harms in summer, cold in winter) + 45 pairwise
               products (possible interactions between stressors)
    fit      = ridge regression weighted by expected deaths, penalty chosen by leave-states-out cross-validation
    interval = cluster bootstrap over states (200 refits): weeks inside a state are strongly dependent, states are not

The model is deliberately transparent, a short list of coefficients, so the browser can evaluate it instantly and every
prediction splits exactly into separate (additive) effects and interaction effects. A gradient-boosting model is trained as a
second opinion, and the honest out-of-sample comparison is stored with the model.

What it is not: a forecast of any one person's risk, and not proof of cause. It estimates the *average association* between
local conditions and weekly state deaths, which is small next to everything else that moves weekly deaths.
"""
from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd

from synera_core.benchmark.generator import STRESSORS
from synera_core.data.health import LOCATIONS, weekly_weighted_mean

HARMONICS = 2
N_BOOT = 200
LAMBDA_MAIN = (0.0, 3.0, 10.0, 30.0, 100.0)        # penalty on the plain effects of each stressor (and heat curvature)
LAMBDA_PRODUCT = (30.0, 300.0, 3000.0)              # penalty on the pairwise products (the uncertain part)
NONNEG = {"precip", "wind", "pm25", "pm10", "o3", "no2", "uv"}
SQUARES = ("heat_index",)           # curvature: the U-shape of temperature
SEASONAL = ("heat_index",)          # effect modified by how hot this time of year normally is
PAIRS = list(itertools.combinations(STRESSORS, 2))
LABELS = {"heat_index": "Heat index", "pm25": "PM2.5", "rh": "Relative humidity", "o3": "Ozone", "drought_index": "Drought index",
          "pm10": "PM10", "no2": "NO2", "uv": "UV index", "wind": "Wind", "precip": "Precipitation"}
UNITS = {"heat_index": "°C", "pm25": "µg/m³", "rh": "%", "o3": "µg/m³", "drought_index": "z-score", "pm10": "µg/m³", "no2": "µg/m³",
         "uv": "index", "wind": "km/h", "precip": "mm/day"}
POLLUTANTS = ("pm25", "pm10", "o3", "no2")
OUTCOMES = {
    "all": {"label": "All causes of death", "panel": "data/processed/us_mortality_panel.parquet", "dataset_id": "us_mortality"},
    "heart": {"label": "Heart disease deaths", "panel": "data/processed/us_heart_panel.parquet", "dataset_id": "us_heart"},
    "stroke": {"label": "Stroke deaths", "panel": "data/processed/us_stroke_panel.parquet", "dataset_id": "us_stroke"},
}


def week_of_year(dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    doy = pd.to_datetime(pd.Series(dates)).dt.dayofyear.to_numpy()
    return np.minimum((doy - 1) // 7, 51).astype(int)


def _harmonic_design(woy: np.ndarray) -> np.ndarray:
    ang = 2 * np.pi * (woy + 0.5) / 52.0
    cols = [np.ones_like(ang)]
    for k in range(1, HARMONICS + 1):
        cols += [np.sin(k * ang), np.cos(k * ang)]
    return np.column_stack(cols)


# ------------------------------------------------------------------------------------------------ climatology
def fit_climatology(panel: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Per state: the normal level of each stressor for each of 52 weeks (smooth annual cycle), the usual deviation around it,
    the expected weekly deaths and how many training weeks cover each week of the year."""
    out: dict[str, dict[str, Any]] = {}
    woy_all = np.arange(52)
    Hall = _harmonic_design(woy_all)
    for state, g in panel.groupby("city", sort=True):
        woy = week_of_year(g["date"])
        H = _harmonic_design(woy)
        clim, sd = {}, {}
        for s in STRESSORS:
            beta, *_ = np.linalg.lstsq(H, g[s].to_numpy(float), rcond=None)
            clim[s] = Hall @ beta
            sd[s] = float(np.std(g[s].to_numpy(float) - H @ beta, ddof=H.shape[1]))
        eb, *_ = np.linalg.lstsq(H, g["expected"].to_numpy(float), rcond=None)
        counts = np.bincount(woy, minlength=52)
        out[state] = {"clim": clim, "sd": sd, "expected_deaths": np.maximum(Hall @ eb, 1.0),
                      "support": [int(counts[np.arange(w - 2, w + 3) % 52].sum()) for w in woy_all], "weeks": int(len(g))}
    return out


def anomaly_frame(panel: pd.DataFrame, clim: dict[str, dict[str, Any]]) -> pd.DataFrame:
    woy = week_of_year(panel["date"])
    cols = {}
    for s in STRESSORS:
        base = np.array([clim[c]["clim"][s][w] for c, w in zip(panel["city"], woy)])
        sd = np.array([clim[c]["sd"][s] for c in panel["city"]])
        cols[s] = (panel[s].to_numpy(float) - base) / sd
    return pd.DataFrame(cols, index=panel.index)


def season_values(panel: pd.DataFrame, clim: dict[str, dict[str, Any]]) -> tuple[np.ndarray, float, float]:
    """How hot this time of year normally is in the state, per row, standardised over the training rows."""
    woy = week_of_year(panel["date"])
    norm = np.array([clim[c]["clim"]["heat_index"][w] for c, w in zip(panel["city"], woy)])
    mu, sd = float(norm.mean()), float(norm.std())
    return (norm - mu) / sd, mu, sd


# ------------------------------------------------------------------------------------------------ terms
def term_names() -> list[dict[str, Any]]:
    t = [{"name": s, "kind": "linear", "a": s} for s in STRESSORS]
    t += [{"name": f"{s}^2", "kind": "square", "a": s} for s in SQUARES]
    t += [{"name": f"{s} x season", "kind": "season_linear", "a": s} for s in SEASONAL]
    t += [{"name": f"{s}^2 x season", "kind": "season_square", "a": s} for s in SEASONAL]
    t += [{"name": f"{a} x {b}", "kind": "product", "a": a, "b": b} for a, b in PAIRS]
    return t


ALL_KINDS = ("linear", "square", "season_linear", "season_square", "product")
NON_PRODUCT = ("linear", "square", "season_linear", "season_square")


def build_terms(z: np.ndarray, season: np.ndarray, kinds: tuple[str, ...] = ALL_KINDS) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Term matrix. ``season`` is, per row, how hot this time of year normally is in the state (standardised)."""
    idx = {s: i for i, s in enumerate(STRESSORS)}
    names = [t for t in term_names() if t["kind"] in kinds]
    cols = []
    for t in names:
        if t["kind"] == "linear":
            cols.append(z[:, idx[t["a"]]])
        elif t["kind"] == "square":
            cols.append(z[:, idx[t["a"]]] ** 2)
        elif t["kind"] == "season_linear":
            cols.append(z[:, idx[t["a"]]] * season)
        elif t["kind"] == "season_square":
            cols.append(z[:, idx[t["a"]]] ** 2 * season)
        else:
            cols.append(z[:, idx[t["a"]]] * z[:, idx[t["b"]]])
    return np.column_stack(cols), names


# ------------------------------------------------------------------------------------------------ fitting
def ridge_fit(T: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float, pen: np.ndarray | None = None
              ) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Weighted ridge on standardised terms -> (weights, intercept, term mean, term scale).

    ``pen`` is a per-term penalty multiplier: the pairwise products (the uncertain part) get a much larger penalty than the plain
    effects of each stressor, so real main effects are not flattened to zero while noisy interactions are."""
    w = w / w.mean()
    m = np.average(T, axis=0, weights=w)
    s = np.sqrt(np.average((T - m) ** 2, axis=0, weights=w))
    s[s == 0] = 1.0
    X = (T - m) / s
    ym = np.average(y, weights=w)
    p = np.ones(X.shape[1]) if pen is None else pen
    A = X.T @ (X * w[:, None]) + np.diag(lam * p * len(y) / 100.0 + 1e-8)
    beta = np.linalg.solve(A, X.T @ ((y - ym) * w))
    return beta, float(ym), m, s


def _predict_terms(T: np.ndarray, beta: np.ndarray, m: np.ndarray, s: np.ndarray, ym: float = 0.0) -> np.ndarray:
    return ((T - m) / s) @ beta + ym


def weighted_r2(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    w = w / w.sum()
    ybar = float(np.sum(w * y))
    return float(1.0 - np.sum(w * (y - p) ** 2) / np.sum(w * (y - ybar) ** 2))


def _state_folds(states: np.ndarray, k: int = 5, seed: int = 1) -> list[np.ndarray]:
    uniq = np.array(sorted(set(states)))
    np.random.default_rng(seed).shuffle(uniq)
    return [np.isin(states, uniq[i::k]) for i in range(k)]


def penalty_vector(terms: list[dict[str, Any]], lam_main: float, lam_product: float) -> np.ndarray:
    return np.array([lam_product if t["kind"] == "product" else lam_main for t in terms], dtype=float)


def cv_penalties(T: np.ndarray, y: np.ndarray, w: np.ndarray, states: np.ndarray, terms: list[dict[str, Any]]
                 ) -> tuple[float, float, dict[str, float]]:
    """Choose the two penalties by leave-states-out cross-validation (prediction error for states not used in fitting)."""
    folds = _state_folds(states)
    score: dict[str, float] = {}
    for lm, lp in itertools.product(LAMBDA_MAIN, LAMBDA_PRODUCT):
        pen = penalty_vector(terms, lm, lp)
        err = 0.0
        for te in folds:
            b, ym, m, s = ridge_fit(T[~te], y[~te], w[~te], 1.0, pen)
            err += float(np.sum(w[te] * (y[te] - _predict_terms(T[te], b, m, s, ym)) ** 2))
        score[f"{lm:g}|{lp:g}"] = err / float(w.sum())
    best = min(score, key=score.get)
    lm, lp = (float(x) for x in best.split("|"))
    return lm, lp, score


def _gbm(Z: np.ndarray, y: np.ndarray, w: np.ndarray):
    import lightgbm as lgb

    return lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1,
                             colsample_bytree=0.8, reg_lambda=5.0, random_state=0, verbose=-1, n_jobs=1).fit(Z, y, sample_weight=w)


def validate(T_full: np.ndarray, T_add: np.ndarray, y: np.ndarray, w: np.ndarray, states: np.ndarray, years: np.ndarray,
             Zx: np.ndarray, pen_full: np.ndarray, pen_add: np.ndarray, seed: int = 7) -> dict[str, Any]:
    """Out-of-sample checks: leave-states-out CV (the real test of 'works for a place it has not seen'), train 2014-17 / test
    2018-19, and a calibration table of predicted vs observed excess deaths from the leave-states-out predictions."""

    def run(train: np.ndarray, test: np.ndarray) -> tuple[dict[str, float], np.ndarray]:
        res = {"null": weighted_r2(y[test], np.full(int(test.sum()), np.average(y[train], weights=w[train])), w[test])}
        pred_full = None
        for name, T, pen in (("additive", T_add, pen_add), ("with_interactions", T_full, pen_full)):
            b, ym, m, s = ridge_fit(T[train], y[train], w[train], 1.0, pen)
            p = _predict_terms(T[test], b, m, s, ym)
            res[name] = weighted_r2(y[test], p, w[test])
            if name == "with_interactions":
                pred_full = p
        res["gradient_boosting"] = weighted_r2(y[test], _gbm(Zx[train], y[train], w[train]).predict(Zx[test]), w[test])
        return res, pred_full

    folds = _state_folds(states)
    per_fold, oos = [], np.zeros(len(y))
    for te in folds:
        r, p = run(~te, te)
        per_fold.append(r)
        oos[te] = p
    out: dict[str, Any] = {
        "leave_states_out": {k: float(np.mean([f[k] for f in per_fold])) for k in per_fold[0]},
        "leave_states_out_by_fold": {k: [float(f[k]) for f in per_fold] for k in per_fold[0]},
        "out_of_time": run(years <= 2017, years >= 2018)[0],
    }
    # calibration: bins of the leave-states-out prediction versus what actually happened
    order = np.argsort(oos)
    bins = np.array_split(order, 10)
    out["deciles"] = [{"predicted": float(np.average(oos[b], weights=w[b])), "observed": float(np.average(y[b], weights=w[b])),
                       "weeks": int(len(b))} for b in bins]

    def slope(idx: np.ndarray) -> float:
        p, o, ww = oos[idx], y[idx], w[idx]
        pm, om = np.average(p, weights=ww), np.average(o, weights=ww)
        return float(np.sum(ww * (p - pm) * (o - om)) / np.sum(ww * (p - pm) ** 2))

    rng = np.random.default_rng(seed)
    uniq = np.array(sorted(set(states)))
    by_state = {u: np.where(states == u)[0] for u in uniq}
    reps = [slope(np.concatenate([by_state[u] for u in rng.choice(uniq, len(uniq))])) for _ in range(200)]
    out["calibration_slope"] = slope(np.arange(len(y)))
    out["calibration_slope_ci"] = [float(np.percentile(reps, 5)), float(np.percentile(reps, 95))]
    return out


def interaction_diagnostic(T: np.ndarray, y: np.ndarray, w: np.ndarray, states: np.ndarray, terms: list[dict[str, Any]], seed: int,
                           n_boot: int = 150) -> dict[str, Any]:
    """Do pairs of stressors act on deaths beyond adding up? Judged on an UNSHRUNKEN fit (shrunken estimates have no valid
    intervals) with a cluster bootstrap over states. Used only for this check, never for predictions."""
    zero = np.zeros(T.shape[1])
    b, _, _, s = ridge_fit(T, y, w, 1.0, zero)
    rng = np.random.default_rng(seed + 1)
    uniq = np.array(sorted(set(states)))
    by_state = {u: np.where(states == u)[0] for u in uniq}
    boots = []
    for _ in range(n_boot):
        idx = np.concatenate([by_state[u] for u in rng.choice(uniq, size=len(uniq), replace=True)])
        bb, _, _, sb = ridge_fit(T[idx], y[idx], w[idx], 1.0, zero)
        boots.append(bb / sb)
    boots = np.array(boots)
    lo, hi = np.percentile(boots, [5, 95], axis=0)
    coef = b / s
    prod = [k for k, t in enumerate(terms) if t["kind"] == "product"]
    rows = [{"term": terms[k]["name"], "a": terms[k]["a"], "b": terms[k]["b"], "coef": float(coef[k]), "lo": float(lo[k]), "hi": float(hi[k]),
             "excludes_zero": bool(lo[k] > 0 or hi[k] < 0)} for k in prod]
    n_sig = sum(r["excludes_zero"] for r in rows)
    strongest = max(rows, key=lambda r: abs(r["coef"]) / max((r["hi"] - r["lo"]) / 3.29, 1e-9))
    return {"pairs_tested": len(rows), "pairs_excluding_zero": int(n_sig), "expected_by_chance": round(0.10 * len(rows), 1),
            "strongest": strongest, "largest_plausible_pct_per_sd2": float(max(max(abs(r["lo"]), abs(r["hi"])) for r in rows)),
            "median_interval_halfwidth": float(np.median([(r["hi"] - r["lo"]) / 2 for r in rows])), "terms": rows}


def _headline(terms, coef, boots_raw, med_sd, seasons) -> list[dict[str, Any]]:
    """What the data say about each stressor on its own, in everyday units, with 90% intervals."""
    idx = {(t["kind"], t["a"]): k for k, t in enumerate(terms) if t["kind"] != "product"}
    rows = []

    def add(sid: str, label: str, step: float, unit: str, z: float, square: bool, direction: str, season: float | None = None,
            season_name: str | None = None) -> None:
        k1 = idx[("linear", sid)]
        eff = coef[k1] * z
        dr = boots_raw[:, k1] * z
        if square:
            k2 = idx[("square", sid)]
            eff += coef[k2] * z * z
            dr = dr + boots_raw[:, k2] * z * z
        if season is not None:
            for kind, zz in (("season_linear", z), ("season_square", z * z)):
                k = idx[(kind, sid)]
                eff += coef[k] * zz * season
                dr = dr + boots_raw[:, k] * zz * season
        rows.append({"stressor": sid, "label": label, "step": float(step), "unit": unit, "direction": direction, "effect": float(eff),
                     "lo": float(np.percentile(dr, 5)), "hi": float(np.percentile(dr, 95)), "season": season_name})

    for s in POLLUTANTS:
        add(s, f"{LABELS[s]} up by 10 {UNITS[s]}", 10.0, UNITS[s], 10.0 / med_sd[s], False, "up")
    z5 = 5.0 / med_sd["heat_index"]
    add("heat_index", "Heat index 5 °C above normal, in summer", 5.0, "°C", z5, True, "up", seasons["summer"], "summer")
    add("heat_index", "Heat index 5 °C below normal, in winter", -5.0, "°C", -z5, True, "down", seasons["winter"], "winter")
    add("heat_index", "Heat index 5 °C above normal, in winter", 5.0, "°C", z5, True, "up", seasons["winter"], "winter")
    add("heat_index", "Heat index 5 °C below normal, in summer", -5.0, "°C", -z5, True, "down", seasons["summer"], "summer")
    for s in ("rh", "drought_index", "uv", "wind", "precip"):
        add(s, f"{LABELS[s]} up by one usual deviation ({med_sd[s]:.3g} {UNITS[s]})", med_sd[s], UNITS[s], 1.0, False, "up")
    return rows


def fit_scenario_model(panel: pd.DataFrame, meta: dict[str, Any] | None = None, n_boot: int = N_BOOT, seed: int = 20260929) -> dict[str, Any]:
    panel = panel.sort_values(["city", "date"]).reset_index(drop=True)
    clim = fit_climatology(panel)
    A = anomaly_frame(panel, clim)
    Az = A.to_numpy(float)
    y = panel["outcome"].to_numpy(float)
    w = panel["expected"].to_numpy(float)
    states = panel["city"].to_numpy()
    years = pd.to_datetime(panel["date"]).dt.year.to_numpy()
    # fit on within-week comparisons: each state's anomaly minus the death-weighted average of all states in that week
    Zt = Az - np.column_stack([weekly_weighted_mean(panel["date"], Az[:, j], w) for j in range(len(STRESSORS))])
    season, season_mean, season_sd = season_values(panel, clim)
    month = pd.to_datetime(panel["date"]).dt.month.to_numpy()
    seasons = {"summer": float(season[np.isin(month, (6, 7, 8))].mean()), "winter": float(season[np.isin(month, (12, 1, 2))].mean())}
    T_full, terms = build_terms(Zt, season)
    T_add, _ = build_terms(Zt, season, NON_PRODUCT)
    lam_main, lam_product, cvscore = cv_penalties(T_full, y, w, states, terms)
    pen = penalty_vector(terms, lam_main, lam_product)
    pen_add = pen[np.array([t["kind"] != "product" for t in terms])]
    beta, ym, m, s = ridge_fit(T_full, y, w, 1.0, pen)
    coef = beta / s

    rng = np.random.default_rng(seed)
    uniq = np.array(sorted(set(states)))
    by_state = {u: np.where(states == u)[0] for u in uniq}
    boots = []
    for _ in range(n_boot):
        idx = np.concatenate([by_state[u] for u in rng.choice(uniq, size=len(uniq), replace=True)])
        b, _, _, sb = ridge_fit(T_full[idx], y[idx], w[idx], 1.0, pen)
        boots.append(b / sb * s)           # stored on the full-data standardised scale so one (mean, scale) serves every replicate
    boots = np.array(boots)
    boots_raw = boots / s
    lo_q, hi_q = np.percentile(boots_raw, [5, 95], axis=0)

    corr = np.corrcoef(Az.T)
    prec = np.linalg.inv(corr + 1e-6 * np.eye(len(STRESSORS)))
    validation = validate(T_full, T_add, y, w, states, years, Zt, pen, pen_add)
    resid = y - _predict_terms(T_full, beta, m, s, ym)
    med_sd = {sn: float(np.median([c["sd"][sn] for c in clim.values()])) for sn in STRESSORS}

    learned = [{"term": t["name"], "kind": t["kind"], "a": t["a"], "b": t.get("b"), "coef": float(c), "lo": float(lo), "hi": float(hi),
                "excludes_zero": bool(lo > 0 or hi < 0)} for t, c, lo, hi in zip(terms, coef, lo_q, hi_q)]
    interaction_check = interaction_diagnostic(T_full, y, w, states, terms, seed)
    locations = {}
    for st, c in clim.items():
        lat, lon = LOCATIONS.get(st, (None, None))
        locations[st] = {"lat": lat, "lon": lon, "clim": {k: np.round(v, 3).tolist() for k, v in c["clim"].items()},
                         "sd": {k: round(v, 4) for k, v in c["sd"].items()}, "expected_deaths": np.round(c["expected_deaths"], 1).tolist(),
                         "support": c["support"], "weeks": c["weeks"]}
    return {
        "stressors": list(STRESSORS), "labels": LABELS, "units": UNITS, "terms": terms, "intercept": ym, "mean": m.tolist(), "scale": s.tolist(),
        "coef": coef.tolist(), "boot": np.round(boots, 5).tolist(), "penalty": {"main": lam_main, "product": lam_product}, "cv_score": cvscore,
        "support": {"precision": prec.round(4).tolist(), "chi2_99": 23.209},   # chi-square 99% quantile, 10 d.f.
        "residual_sd": float(np.sqrt(np.average(resid ** 2, weights=w))), "locations": locations, "learned_terms": learned,
        "headline": _headline(terms, coef, boots_raw, med_sd, seasons), "season": {"mean": season_mean, "sd": season_sd, **seasons}, "interaction_check": interaction_check, "validation": validation,
        "training": {"rows": int(len(panel)), "states": int(len(uniq)), "date_start": str(pd.to_datetime(panel["date"]).min().date()),
                     "date_end": str(pd.to_datetime(panel["date"]).max().date()), "bootstrap_replicates": int(n_boot)},
        "anomaly_sd_pooled": {sn: float(np.std(A[sn])) for sn in STRESSORS}, **(meta or {}),
    }


# ------------------------------------------------------------------------------------------------ prediction (reference implementation)
def _terms_for(z: np.ndarray, season: float) -> np.ndarray:
    return build_terms(z.reshape(1, -1), np.array([season]))[0][0]


def predict(model: dict[str, Any], state: str, woy: int, levels: dict[str, float] | None = None,
            anomalies: dict[str, float] | None = None) -> dict[str, Any]:
    """Effect of the given conditions versus a typical week in ``state`` (week index 0-51).

    ``levels`` are absolute values (physical units); any stressor left out stays at the state's normal for that week.
    ``anomalies`` (in the state's usual deviations) may be given instead. The national picture that week is assumed typical.
    The TypeScript twin in frontend/src/lib/scenario.ts must give the same numbers (tests compare them)."""
    loc = model["locations"][state]
    names = model["stressors"]
    z = np.zeros(len(names))
    levels_abs = {}
    for i, s in enumerate(names):
        normal = loc["clim"][s][woy]
        if anomalies and s in anomalies:
            z[i] = anomalies[s]
            levels_abs[s] = normal + anomalies[s] * loc["sd"][s]
        elif levels and levels.get(s) is not None:
            z[i] = (levels[s] - normal) / loc["sd"][s]
            levels_abs[s] = levels[s]
        else:
            levels_abs[s] = normal
    season = (loc["clim"]["heat_index"][woy] - model["season"]["mean"]) / model["season"]["sd"]
    d = _terms_for(z, season)                          # at zero anomaly every term is zero, so the terms are the difference
    coef = np.array(model["coef"])
    boot = np.array(model["boot"]) / np.array(model["scale"])
    draws = boot @ d
    kinds = np.array([tt["kind"] for tt in model["terms"]])
    prod = kinds == "product"
    contrib = {s: 0.0 for s in names}
    for tt, di, ci in zip(model["terms"], d, coef):
        if tt["kind"] == "product":
            contrib[tt["a"]] += 0.5 * di * ci
            contrib[tt["b"]] += 0.5 * di * ci
        else:
            contrib[tt["a"]] += di * ci
    inter_draws = boot[:, prod] @ d[prod]
    maha = float(z @ np.array(model["support"]["precision"]) @ z)
    exp_deaths = loc["expected_deaths"][woy]
    effect = float(d @ coef)
    return {
        "effect_pct": effect, "lo_pct": float(np.percentile(draws, 5)), "hi_pct": float(np.percentile(draws, 95)),
        "additive_pct": float(d[~prod] @ coef[~prod]), "interaction_pct": float(d[prod] @ coef[prod]),
        "interaction_lo_pct": float(np.percentile(inter_draws, 5)), "interaction_hi_pct": float(np.percentile(inter_draws, 95)),
        "contributions": contrib, "extra_deaths_per_week": effect / 100.0 * exp_deaths, "expected_deaths_per_week": exp_deaths,
        "anomalies": dict(zip(names, z.tolist())), "levels": levels_abs,
        "support": {"mahalanobis_sq": maha, "unusual": bool(maha > model["support"]["chi2_99"]), "max_abs_anomaly": float(np.max(np.abs(z)))},
        "season_covered": bool(loc["support"][woy] >= 6),
    }
