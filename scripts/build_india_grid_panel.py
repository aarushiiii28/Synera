"""Build the REAL India electricity-demand panels (Track D): daily energy supplied to each Indian state, joined to the state's weather.

    python scripts/build_india_grid_panel.py       # downloads once (cached under data/raw/india_grid), then offline

Source (one public record, CC BY 4.0): K. Hunt and H. Bloomfield, "Daily electricity demand data for Indian states (2014-2024)",
Zenodo, doi 10.5281/zenodo.14983362. Demand is Grid-India (POSOCO) daily energy met per state; the weather columns are state-level ERA5
daily statistics from the same record. Nothing is simulated and nothing is imputed.

Two panels, 8 states each, so that what one shows can be checked on the other:
  india_grid    Maharashtra, Gujarat, Uttar Pradesh, Tamil Nadu, Rajasthan, Karnataka, Delhi, Punjab   (the 8 largest by demand, chosen by size)
  india_grid_b  Madhya Pradesh, Andhra Pradesh, Telangana, West Bengal, Odisha, Bihar, Kerala, Haryana

Outcome = % above the state's own expected demand (log demand ~ trend + 3 annual harmonics + day of week). Unlike the US death panels there
is no nationwide wave (such as flu) that must be removed, so the analysed ``outcome`` stops there. ``outcome_nat`` is a sensitivity version that
also subtracts the demand-weighted average of the panel's states on the same day (it removes national holidays and nationwide weather, and with
them much of the shared weather response). Both were run on both panels and they do NOT select the same pairs; that difference is reported, not hidden.
"""
from __future__ import annotations

import json
import sys

import httpx
import numpy as np
import pandas as pd

from synera_core.config import find_repo_root
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger

ROOT = find_repo_root()
RAW = ROOT / "data" / "raw" / "india_grid"
PROC = ROOT / "data" / "processed"
BASE = "https://zenodo.org/records/14983362/files/{}?download=1"
START, END = pd.Timestamp("2019-01-01"), pd.Timestamp("2024-04-28")
MIN_DAYS = 1000          # a state needs about three years of days to estimate its own normal
STRESS = ["tmax", "rh", "wind", "solar", "cloud"]

# demand column in the national file -> weather file stem
GROUPS = {
    "india_grid": {"Maharashtra": "Maharashtra", "Gujarat": "Gujarat", "Uttar Pradesh": "Uttar_Pradesh", "Tamil Nadu": "Tamil_Nadu",
                   "Rajasthan": "Rajasthan", "Karnataka": "Karnataka", "Delhi": "NCT_of_Delhi", "Punjab": "Punjab"},
    "india_grid_b": {"Madhya Pradesh": "Madhya_Pradesh", "Andhra Pradesh": "Andhra_Pradesh", "Telangana": "Telangana", "West Bengal": "West_Bengal",
                     "Odisha": "Odisha", "Bihar": "Bihar", "Kerala": "Kerala", "Haryana": "Haryana"},
}


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch(name: str) -> None:
    p = RAW / name
    if p.exists():
        return
    log(f"  downloading {name} ...")
    for attempt in range(4):
        try:
            r = httpx.get(BASE.format(name), timeout=180, follow_redirects=True)
            r.raise_for_status()
            p.write_bytes(r.content)
            return
        except httpx.HTTPError as exc:
            if attempt == 3:
                raise RuntimeError(f"could not download {name}: {exc}") from exc


def rh_from(t: pd.Series, td: pd.Series) -> pd.Series:
    """Relative humidity (%) from air and dew-point temperature (deg C), Magnus formula."""
    return (100 * np.exp(17.625 * td / (243.04 + td)) / np.exp(17.625 * t / (243.04 + t))).clip(0, 100)


def weather(stem: str) -> pd.DataFrame:
    w = pd.read_csv(RAW / f"{stem}.csv", parse_dates=["date"]).set_index("date")
    t, td = w["2m_temperature_mean"] - 273.15, w["2m_dewpoint_temperature_mean"] - 273.15
    return pd.DataFrame({
        "tmax": w["2m_temperature_max"] - 273.15,                                                # deg C
        "rh": rh_from(t, td),                                                                    # %
        "wind": np.hypot(w["10m_u_component_of_wind_mean"], w["10m_v_component_of_wind_mean"]),  # m/s
        "solar": w["surface_solar_radiation_downwards_mean"] / 3.6e6,                            # J/m2 -> kWh/m2 per day
        "cloud": w["total_cloud_cover_mean"],                                                    # fraction 0..1
    })


def expected_log(dates: pd.Series, y: np.ndarray) -> np.ndarray:
    """The state's own expected log demand: linear trend + 3 annual harmonics + day of week."""
    t = (dates - dates.iloc[0]).dt.days.to_numpy(float) / 365.25
    doy = dates.dt.dayofyear.to_numpy(float)
    cols = [np.ones_like(t), t]
    for k in (1, 2, 3):
        cols += [np.sin(2 * np.pi * k * doy / 365.25), np.cos(2 * np.pi * k * doy / 365.25)]
    dow = dates.dt.dayofweek.to_numpy()
    cols += [(dow == d).astype(float) for d in range(1, 7)]
    X = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return X @ beta


def build(group: dict[str, str], demand: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows, dropped = [], {}
    for state, stem in group.items():
        s = demand[state].dropna()
        s = s[(s.index >= START) & (s.index <= END) & (s > 0)]
        d = pd.DataFrame({"city": state, "date": s.index, "demand_mu": s.to_numpy()}).join(weather(stem), on="date").dropna(subset=STRESS)
        if len(d) < MIN_DAYS:
            dropped[state] = int(len(d))
            continue
        fit = expected_log(d["date"].reset_index(drop=True), np.log(d["demand_mu"].to_numpy()))
        d["outcome_raw"] = 100.0 * (np.log(d["demand_mu"].to_numpy()) - fit)
        d["expected_mu"] = np.exp(fit)
        rows.append(d)
    p = pd.concat(rows, ignore_index=True)
    w = p["expected_mu"]
    mean_day = (p["outcome_raw"] * w).groupby(p["date"]).transform("sum") / w.groupby(p["date"]).transform("sum")
    p["outcome_nat"] = p["outcome_raw"] - mean_day          # sensitivity version: same-day average of the panel's states removed
    p["outcome"] = p["outcome_raw"]                         # the analysed outcome: the state's own trend, season and weekday removed
    p = p[["city", "date", *STRESS, "outcome", "outcome_nat", "demand_mu", "expected_mu"]].sort_values(["city", "date"]).reset_index(drop=True)
    return p, dropped


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    log("1. downloading the Zenodo record files (cached)")
    fetch("corrected_daily_energy_met_MU.csv")
    for g in GROUPS.values():
        for stem in g.values():
            fetch(f"{stem}.csv")
    demand = pd.read_csv(RAW / "corrected_daily_energy_met_MU.csv", parse_dates=["Date"])
    n_dup = int(demand["Date"].duplicated().sum())
    demand = demand.drop_duplicates("Date").set_index("Date")      # the source repeats some dates with identical values
    cal_days = (demand.index.max() - demand.index.min()).days + 1
    log(f"   source: {len(demand)} distinct days of {cal_days} in the calendar span ({n_dup} repeated dates dropped; absent days stay absent)")
    ledger = open_ledger()
    manifest = ROOT / "data" / "MANIFEST.json"
    PROC.mkdir(parents=True, exist_ok=True)
    for did, group in GROUPS.items():
        p, dropped = build(group, demand)
        out = PROC / f"{did}_panel.parquet"
        p.to_parquet(out, index=False)
        qc = {
            "title": f"India daily electricity supplied x state weather, {len(group)} states, {START.date()} to {END.date()}",
            "provenance": "REAL", "rows": int(len(p)), "states": sorted(p["city"].unique().tolist()),
            "date_start": str(p["date"].min().date()), "date_end": str(p["date"].max().date()),
            "days_per_state": {k: int(v) for k, v in p.groupby("city").size().items()}, "states_dropped_for_too_few_days": dropped,
            "source_repeated_dates_dropped": n_dup,
            "sources": {"demand": "Grid-India (POSOCO) daily energy met per state, as packaged and quality-checked by Hunt and Bloomfield, Zenodo 10.5281/zenodo.14983362, CC BY 4.0",
                        "weather": "state-level daily statistics of ERA5 (temperature, dew point, wind, solar radiation, cloud cover), same Zenodo record"},
            "stressors": {"tmax": "daily maximum 2 m temperature, deg C", "rh": "relative humidity from mean temperature and dew point, %",
                          "wind": "mean 10 m wind speed, m/s", "solar": "surface solar radiation, kWh/m2/day", "cloud": "mean total cloud cover, 0 to 1"},
            "outcome": "% above the state's own expected electricity supplied (log demand ~ linear trend + 3 annual harmonics + day of week); outcome_nat additionally subtracts the demand-weighted average of this panel's states on the same day (a sensitivity version)",
            "construction_choice": "The analysed outcome (without the same-day subtraction) was chosen after both versions had been run on both panels, because no nationwide wave comparable to flu exists for electricity; the two versions select different pairs, so the pairs found are not robust to this choice.",
            "limitations": [
                "The outcome is electricity supplied to the grid, not health: it measures stress on the power system.",
                "Weather is a state-level ERA5 average, not each city's own conditions.",
                "Solar radiation and cloud cover move together and both track humidity; pairs involving them may reflect weather regimes (for example humid, cloudy monsoon days), not one clean mechanism.",
                "Farm pumping and other non-cooling loads also respond to weather and are not separated out.",
                "The same record supplies demand and weather for both panels: replication across states is not replication across data sources.",
                "About 6% of calendar days are absent from the source and are left absent."],
        }
        qc_path = PROC / f"{did}_panel_qc.json"
        qc_path.write_text(json.dumps(qc, indent=2), encoding="utf-8")
        for pth in (out, qc_path):
            register_file(ledger, pth, "dataset", {"provenance": "REAL", "description": "India daily electricity supplied x weather (Track D)"}, manifest_path=manifest)
        log(f"2. {did}: {len(p)} state-days in {p['city'].nunique()} states -> {out.name} ({out.stat().st_size / 1e6:.2f} MB); registered in the ledger"
            + (f"; dropped {dropped}" if dropped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
