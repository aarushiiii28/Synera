"""Environmental risk brief from validated interaction findings.

For a region (one of the benchmark cities) we take the current + 7-day forecast of every stressor, express
it in the same per-city standardised units the findings were fitted in, and evaluate each finding's stored
response surface at the forecast values:

    additive expectation   z_additive(a, b)      what the two stressors do independently
    modelled response      z_full(a, b)          what the fitted surface predicts
    interaction uplift     z_full - z_additive   the part attributable to the interaction

Units are outcome standard deviations of the model the finding came from. The risk tier is the percentile of
today's summed uplift within the region's own history on the same surfaces (LOW < 50th, MODERATE < 80th,
HIGH < 95th, SEVERE otherwise). The uncertainty band rescales the uplift by the bootstrap CI of the finding's
effect size. A tier is never returned without its band and its source finding ids.

Findings from SIMULATED data produce ``simulated_only = True``; no verified real-world interaction exists
in this repository, and the response says so.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from synera_core.benchmark.generator import STRESSORS, load_env_panel
from synera_core.config import find_repo_root
from synera_core.data.cities import CITIES, calculate_heat_index

CACHE_TTL_S = 6 * 3600
TIERS = [(0.95, "SEVERE"), (0.80, "HIGH"), (0.50, "MODERATE"), (0.0, "LOW")]


def _cache_path(region: str) -> Path:
    d = find_repo_root() / "artifacts" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"forecast_{region.replace(' ', '_')}.json"


def _fetch_live(region: str) -> pd.DataFrame:
    c = CITIES[region]
    base = {"latitude": c["lat"], "longitude": c["lon"], "past_days": 30, "forecast_days": 7, "timezone": "UTC"}
    with httpx.Client(timeout=20, headers={"User-Agent": "SYNERA/1.0 (research)"}) as client:
        w = client.get("https://api.open-meteo.com/v1/forecast", params={
            **base, "daily": "temperature_2m_mean,relative_humidity_2m_mean,precipitation_sum,wind_speed_10m_max"})
        w.raise_for_status()
        a = client.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            **base, "hourly": "pm2_5,pm10,ozone,nitrogen_dioxide,uv_index"})
        a.raise_for_status()
    wd = pd.DataFrame(w.json()["daily"]).rename(columns={
        "time": "date", "temperature_2m_mean": "tmean", "relative_humidity_2m_mean": "rh",
        "precipitation_sum": "precip", "wind_speed_10m_max": "wind"})
    ah = pd.DataFrame(a.json()["hourly"])
    ah["date"] = pd.to_datetime(ah["time"]).dt.strftime("%Y-%m-%d")
    ad = ah.drop(columns=["time"]).groupby("date").mean().reset_index().rename(columns={
        "pm2_5": "pm25", "ozone": "o3", "nitrogen_dioxide": "no2", "uv_index": "uv"})
    return wd.merge(ad, on="date", how="left")


def get_forecast(region: str, offline: bool = False) -> tuple[pd.DataFrame, dict]:
    """Daily stressor frame (last 30 observed days + 7 forecast days) and a ``source`` description."""
    cp = _cache_path(region)
    cached = json.loads(cp.read_text()) if cp.exists() else None
    if cached and (offline or time.time() - cached["ts"] < CACHE_TTL_S):
        return pd.DataFrame(cached["rows"]), {"mode": "cached", "fetched_at": cached["ts"]}
    if not offline:
        try:
            df = _fetch_live(region)
            cp.write_text(json.dumps({"ts": time.time(), "rows": df.to_dict(orient="records")}))
            return df, {"mode": "live", "fetched_at": time.time()}
        except Exception as exc:  # noqa: BLE001 - network failure is an expected, reported condition
            err = str(exc)
        else:
            err = ""
        if cached:
            return pd.DataFrame(cached["rows"]), {"mode": "cached", "fetched_at": cached["ts"], "note": f"live fetch failed: {err}"}
    # Last resort: the final 37 days of the real archive panel. Clearly labelled; nothing is invented.
    panel = load_env_panel()
    g = panel[panel["city"] == region].tail(37)
    return g[["date", "tmean", "rh", "precip", "wind", "pm25", "o3", "no2", "uv", "pm10"]].assign(
        date=lambda d: d["date"].dt.strftime("%Y-%m-%d")), {
        "mode": "archive_fallback", "note": "No live or cached forecast available; showing the last 37 days of the archive panel (2023)."}


def _climatology(region: str) -> tuple[dict[str, tuple[float, float]], pd.DataFrame]:
    panel = load_env_panel()
    g = panel[panel["city"] == region]
    return {s: (float(g[s].mean()), float(g[s].std() + 1e-9)) for s in STRESSORS}, g


def _stressor_frame(region: str, raw: pd.DataFrame) -> pd.DataFrame:
    """Derive heat_index and drought_index like the archive panel and standardise per city."""
    clim, g = _climatology(region)
    d = raw.copy().sort_values("date").reset_index(drop=True)
    d["heat_index"] = calculate_heat_index(d["tmean"], d["rh"])
    p30 = d["precip"].rolling(30, min_periods=1).sum()
    ref = g["precip"].rolling(30, min_periods=1).sum()
    d["drought_index"] = -(p30 - ref.mean()) / (ref.std() + 1e-9)
    z = pd.DataFrame({"date": d["date"]})
    for s in STRESSORS:
        if s == "drought_index":
            z[s] = d[s]            # already standardised against the city's own 30-day-precip climatology
        elif s in d:
            m, sd = clim[s]
            z[s] = (d[s] - m) / sd
    return z


def _interp(surface: dict, key: str):
    return RegularGridInterpolator((np.asarray(surface["grid_b"]), np.asarray(surface["grid_a"])),
                                   np.asarray(surface[key]), bounds_error=False, fill_value=None)


def _tier(pct: float) -> str:
    return next(name for cut, name in TIERS if pct >= cut)


def evaluate_risk(region: str, findings: list[dict], offline: bool = False) -> dict[str, Any]:
    """``findings``: dicts with ``id``, ``provenance``, ``status``, ``stressors`` [a, b], ``surface``, ``effect``."""
    if region not in CITIES:
        raise KeyError(region)
    usable = [f for f in findings if f.get("surface") and f["status"] in ("VALIDATED", "VERIFIED")]
    raw, source = get_forecast(region, offline=offline)
    out: dict[str, Any] = {"region": region, "source": source, "n_findings_used": len(usable),
                           "source_findings": [f["id"] for f in usable]}
    if not usable:
        return {**out, "simulated_only": True, "risk_tier": None, "available": False,
                "message": "No VALIDATED or VERIFIED interaction findings exist, so no compound-risk estimate can be made."}

    z = _stressor_frame(region, raw)
    last7 = z.tail(7).reset_index(drop=True)
    _, hist = _climatology(region)
    hist_z = pd.DataFrame({s: (hist[s] - hist[s].mean()) / (hist[s].std() + 1e-9) for s in STRESSORS})

    daily_up = np.zeros(len(last7))
    daily_add = np.zeros(len(last7))
    daily_full = np.zeros(len(last7))
    hist_up = np.zeros(len(hist_z))
    lo_scale, hi_scale = [], []
    for f in usable:
        a, b = f["stressors"]
        s = f["surface"]
        gap, add, full = _interp(s, "z_gap"), _interp(s, "z_additive"), _interp(s, "z_full")
        pts = np.column_stack([last7[b].to_numpy(), last7[a].to_numpy()])
        daily_up += gap(pts)
        daily_add += add(pts)
        daily_full += full(pts)
        hist_up += gap(np.column_stack([hist_z[b].to_numpy(), hist_z[a].to_numpy()]))
        eff = f["effect"].get("effect_size") or 0.0
        if eff > 0:
            lo_scale.append(f["effect"].get("eff_ci_low", eff) / eff)
            hi_scale.append(f["effect"].get("eff_ci_high", eff) / eff)
    pct = np.array([(hist_up <= u).mean() if np.isfinite(u) else np.nan for u in daily_up])
    lo_s = float(np.mean(lo_scale)) if lo_scale else 1.0
    hi_s = float(np.mean(hi_scale)) if hi_scale else 1.0
    if not np.isfinite(daily_up[0]):
        return {**out, "available": False, "simulated_only": True, "risk_tier": None,
                "message": "Today's stressor values are incomplete (missing forecast fields), so no estimate is made."}
    simulated_only = all(f["provenance"] == "SIMULATED" for f in usable)
    verified_real = [f["id"] for f in usable if f["status"] == "VERIFIED" and f["provenance"] == "REAL"]
    return {
        **out, "available": True, "simulated_only": simulated_only, "verified_real_findings": verified_real,
        "units": "outcome SD of the simulated benchmark model" if simulated_only else "outcome SD",
        "risk_tier": _tier(float(pct[0])), "risk_percentile": float(pct[0]),
        "interaction_uplift": float(daily_up[0]),
        "uncertainty_lower": float(min(daily_up[0] * lo_s, daily_up[0] * hi_s)),
        "uncertainty_upper": float(max(daily_up[0] * lo_s, daily_up[0] * hi_s)),
        "uncertainty_basis": "uplift rescaled by the block-bootstrap 95% CI of each finding's effect size",
        "tier_basis": f"percentile of summed interaction uplift within {region}'s {len(hist_z)}-day history on the same surfaces",
        "forecast": [{
            "date": str(last7["date"].iloc[i]),
            "additive": float(daily_add[i]), "modelled": float(daily_full[i]), "uplift": float(daily_up[i]),
            "percentile": None if np.isnan(pct[i]) else float(pct[i]),
            "tier": None if np.isnan(pct[i]) else _tier(float(pct[i])),
            "stressors": {s: (None if pd.isna(last7[s].iloc[i]) else float(last7[s].iloc[i])) for s in STRESSORS},
        } for i in range(len(last7))],
    }
