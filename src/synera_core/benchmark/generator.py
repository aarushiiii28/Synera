"""Semi-synthetic benchmark: REAL environmental covariates, SIMULATED outcome.

The outcome is built from the real stressor panel (standardised per city) as

    y = city effect + seasonality + main effects + planted interactions + decoy main effects + AR(1) noise

with a known truth table, so the discovery engine can be scored for precision, recall and false
discovery rate. Every row carries ``provenance == "SIMULATED"``. The real covariates on disk are
never modified.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from synera_core.config import find_repo_root
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import register_file

STRESSORS = ["heat_index", "pm25", "rh", "o3", "drought_index", "pm10", "no2", "uv", "wind", "precip"]

# (var1, var2, type, coefficient on the standardised product / switch term)
PLANTED = [
    ("heat_index", "pm25", "SYNERGISTIC", 1.5),
    ("heat_index", "rh", "ANTAGONISTIC", -1.5),
    ("o3", "heat_index", "NONLINEAR", 2.0),
]


def load_env_panel(path: Path | None = None) -> pd.DataFrame:
    """Load the real environmental panel, sorted by (city, date), with complete stressor rows only.

    Rows with missing stressor values are dropped explicitly (never imputed).
    """
    path = path or (find_repo_root() / "data" / "processed" / "env_panel.parquet")
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=STRESSORS).sort_values(["city", "date"]).reset_index(drop=True)
    return df


def standardise_per_city(df: pd.DataFrame, cols: list[str] = STRESSORS) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        g = out.groupby("city")[c]
        out[c] = (out[c] - g.transform("mean")) / (g.transform("std") + 1e-9)
    return out


def simulate_benchmark(env_df: pd.DataFrame, snr: float = 2.0, rho: float = 0.5, seed: int = 42,
                       n_decoys: int = 5, null: bool = False) -> tuple[pd.DataFrame, dict]:
    """Simulate the outcome on real covariates. Returns ``(dataframe, truth)``.

    ``snr`` is signal variance / noise variance. With ``null=True`` no interactions are planted
    (main effects, city effects and seasonality remain), which is what null calibration uses.
    ``env_df`` must already be per-city standardised and sorted by (city, date).
    """
    rng = np.random.default_rng(seed)
    df = env_df.copy().reset_index(drop=True)
    n = len(df)
    doy = pd.to_datetime(df["date"]).dt.dayofyear.to_numpy(float)
    y = np.zeros(n)

    cities = list(df["city"].unique())
    city_effects = {c: rng.normal(0, 1) for c in cities}
    y += df["city"].map(city_effects).to_numpy()
    y += np.sin(2 * np.pi * doy / 365.25) + np.cos(2 * np.pi * doy / 365.25)

    for var in ("heat_index", "pm25", "rh", "o3"):
        y += 0.5 * df[var].to_numpy()

    truth: dict = {"interactions": [], "decoys": [], "null": bool(null), "seed": seed, "snr": snr, "rho": rho}
    if not null:
        for v1, v2, kind, coef in PLANTED:
            if kind == "NONLINEAR":
                switch = 1.0 / (1.0 + np.exp(-3.0 * df["heat_index"].to_numpy()))
                y += coef * df[v1].to_numpy() * switch
            else:
                y += coef * df[v1].to_numpy() * df[v2].to_numpy()
            truth["interactions"].append({"var1": v1, "var2": v2, "type": kind, "effect": coef})

    decoy_candidates = ["drought_index", "pm10", "no2", "uv", "wind", "precip"]
    for dc in rng.choice(decoy_candidates, min(n_decoys, len(decoy_candidates)), replace=False):
        eff = float(rng.choice([1.0, -1.0]))
        y += eff * df[dc].to_numpy()
        truth["decoys"].append({"var": str(dc), "effect": eff})

    noise = np.zeros(n)
    for city in cities:
        idx = np.where(df["city"].to_numpy() == city)[0]
        e = rng.normal(0, 1, len(idx))
        z = np.empty(len(idx))
        z[0] = e[0]
        for t in range(1, len(idx)):
            z[t] = rho * z[t - 1] + np.sqrt(1 - rho ** 2) * e[t]
        noise[idx] = z
    noise *= np.sqrt(np.var(y) / snr)

    df["outcome"] = y + noise
    df["provenance"] = "SIMULATED"
    return df, truth


def label_pairs(df: pd.DataFrame, truth: dict, stressors: list[str] = STRESSORS,
                r_proxy: float = 0.6) -> dict[tuple[str, str], str]:
    """Label every stressor pair: ``true`` | ``proxy`` | ``hard_decoy`` | ``easy_decoy``.

    * ``true``       - a planted interaction.
    * ``proxy``      - not planted, but each member is (or is strongly correlated, |r| >= ``r_proxy``,
                       with) a different member of one planted pair. Such a pair cannot be told apart
                       from the planted one by construction, so it is reported separately.
    * ``hard_decoy`` - touches a planted variable but is not a proxy.
    * ``easy_decoy`` - touches no planted variable.
    """
    corr = df[stressors].corr().abs()
    planted = [(it["var1"], it["var2"]) for it in truth["interactions"]]
    planted_vars = {v for pr in planted for v in pr}
    true_keys = {tuple(sorted(pr)) for pr in planted}
    out: dict[tuple[str, str], str] = {}
    for i, a in enumerate(stressors):
        for b in stressors[i + 1:]:
            if tuple(sorted((a, b))) in true_keys:
                out[(a, b)] = "true"
                continue
            is_proxy = any(
                (corr.loc[a, p] >= r_proxy and corr.loc[b, q] >= r_proxy)
                or (corr.loc[a, q] >= r_proxy and corr.loc[b, p] >= r_proxy)
                for p, q in planted
            )
            if is_proxy:
                out[(a, b)] = "proxy"
            elif a in planted_vars or b in planted_vars:
                out[(a, b)] = "hard_decoy"
            else:
                out[(a, b)] = "easy_decoy"
    return out

def generate_benchmark(snr: float = 2.0, rho: float = 0.5, n_per_city: int | None = None,
                       n_decoys: int = 5, seed: int = 42, out_dir: Path | None = None,
                       ledger: Ledger | None = None) -> tuple[Path, Path]:
    """Write one benchmark dataset and its truth table to ``data/synthetic`` (optionally ledger-registered).

    ``n_per_city`` takes a contiguous window per city (date order preserved); ``None`` uses the full panel.
    """
    out_dir = out_dir or (find_repo_root() / "data" / "synthetic")
    out_dir.mkdir(parents=True, exist_ok=True)
    env = load_env_panel()
    if n_per_city:
        rng = np.random.default_rng(seed)
        parts = []
        for _, g in env.groupby("city", sort=False):
            if n_per_city >= len(g):
                parts.append(g)
            else:
                s = int(rng.integers(0, len(g) - n_per_city + 1))
                parts.append(g.iloc[s:s + n_per_city])
        env = pd.concat(parts).reset_index(drop=True)
    env = standardise_per_city(env)
    df, truth = simulate_benchmark(env, snr=snr, rho=rho, seed=seed, n_decoys=n_decoys)
    out_path = out_dir / f"benchmark_snr{snr}_seed{seed}.parquet"
    df.to_parquet(out_path, index=False)
    truth_path = out_dir / f"benchmark_truth_snr{snr}_seed{seed}.json"
    truth_path.write_text(json.dumps(truth, indent=2))
    if ledger:
        register_file(ledger, out_path, "dataset", {"snr": snr, "rho": rho, "seed": seed, "provenance": "SIMULATED"})
        register_file(ledger, truth_path, "dataset", {"type": "truth", "seed": seed})
    return out_path, truth_path

