"""A city's own normal for this time of year, from three years of Open-Meteo history, and how far the live week sits from it.

The scenario model works in *anomalies*: how far this week's conditions are from the normal for the place and season, in units of the place's usual
variation. For a US state that normal comes from the model file. For an Indian city it is computed here, the same way: the trailing 7-day mean of each
stressor over the same calendar window (plus or minus ``HALF`` days) of 2023-2025, whose mean is the normal and whose standard deviation is the usual variation.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

HALF = 10                 # days either side of today's calendar date
MIN_N = 30                # rolling weeks needed before a normal is trusted
# model stressor -> column in the stored daily history
SOURCE_COLUMN = {"heat_index": "apparent_temperature_max", "rh": "relative_humidity_2m_mean", "precip": "precipitation_sum", "wind": "wind_speed_10m_max",
                 "pm25": "pm2_5", "pm10": "pm10", "o3": "ozone", "no2": "nitrogen_dioxide"}
NOT_AVAILABLE = {"uv": "the model's UV input is NASA POWER all-sky UV, a different quantity from the forecast UV index, so it stays at normal",
                 "drought_index": "needs a 30-day rainfall climatology that is not computed for live use, so it stays at normal"}


def _circular_gap(doy: pd.Series, target: int) -> pd.Series:
    d = (doy - target).abs()
    return np.minimum(d, 365 - d)


def normals(history: dict[str, list], today: pd.Timestamp) -> dict[str, Any]:
    """{stressor: {mean, sd, n}} for the weekly mean of each stressor around today's calendar date, and the daily Tmax normal for departures."""
    df = pd.DataFrame(history)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    near = _circular_gap(pd.Series(df.index.dayofyear, index=df.index), int(today.dayofyear)) <= HALF
    out: dict[str, Any] = {}
    for s, col in SOURCE_COLUMN.items():
        if col not in df:
            continue
        weekly = df[col].astype(float).rolling(7, min_periods=5).mean()
        v = weekly[near].dropna()
        if len(v) >= MIN_N and float(v.std(ddof=1)) > 0:
            out[s] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1)), "n": int(len(v))}
    tmax = df["temperature_2m_max"].astype(float)[near].dropna() if "temperature_2m_max" in df else pd.Series(dtype=float)
    out["_tmax"] = {"mean": float(tmax.mean()), "sd": float(tmax.std(ddof=1)), "n": int(len(tmax))} if len(tmax) >= MIN_N else None
    return out


def live_week(w: dict, a: dict | None, today: pd.Timestamp) -> dict[str, float | None]:
    """Mean over the last 7 days (to now) of each stressor, built the way the training weeks were: daily apparent-temperature maximum, daily mean humidity,
    daily rain total, daily maximum wind, daily mean pollutant."""
    hw = pd.DataFrame({"time": pd.to_datetime(w["hourly"]["time"]), "rh": w["hourly"]["relative_humidity_2m"]}).dropna()
    hw["day"] = hw["time"].dt.normalize()
    rh_daily = hw.groupby("day")["rh"].mean()
    d = w["daily"]
    days = pd.to_datetime(d["time"])
    daily = pd.DataFrame({"heat_index": d["apparent_temperature_max"], "precip": d["precipitation_sum"], "wind": d["wind_speed_10m_max"]}, index=days)
    daily["rh"] = rh_daily.reindex(days).to_numpy()
    if a and "hourly" in a:
        ha = pd.DataFrame({"time": pd.to_datetime(a["hourly"]["time"]), "pm25": a["hourly"]["pm2_5"], "pm10": a["hourly"]["pm10"], "o3": a["hourly"]["ozone"],
                           "no2": a["hourly"]["nitrogen_dioxide"]})
        ha["day"] = ha["time"].dt.normalize()
        for c in ("pm25", "pm10", "o3", "no2"):
            daily[c] = ha.groupby("day")[c].mean().reindex(days).to_numpy()
    week = daily[daily.index <= today.normalize()].tail(7)
    return {c: (float(week[c].mean()) if week[c].notna().sum() >= 5 else None) for c in daily.columns}


def anomalies(live: dict[str, float | None], norm: dict[str, Any]) -> tuple[dict[str, float], dict[str, str]]:
    """z = (live week - normal) / usual variation, for the stressors for which both exist; and why the others are left at normal."""
    z, why = {}, {}
    for s in SOURCE_COLUMN:
        if live.get(s) is None:
            why[s] = "no live value for the week"
        elif s not in norm:
            why[s] = "no usable normal for this city and season"
        else:
            z[s] = (live[s] - norm[s]["mean"]) / norm[s]["sd"]
    why.update(NOT_AVAILABLE)
    return z, why
