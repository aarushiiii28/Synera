"""Provider payloads -> one validated, labelled reading per city.

Every metric carries its unit, where it came from and what kind of number it is, so the interface can keep three things apart:

* ``OBSERVATION``     measured at a station (CPCB, OpenAQ)
* ``MODEL_ANALYSIS``  the current state estimated by a weather / air-quality model from observations and satellites (Open-Meteo, CAMS). Not a
                      station reading; for air quality it can differ from the nearest monitor.
* ``FORECAST``        a model's prediction for a future hour or day
* ``DERIVED``         computed by SYNERA from the above with a published formula (AQI, heat index, categories)

Values outside physical limits are dropped and reported, never clipped into plausibility.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from synera_core.data.cities import calculate_heat_index
from synera_core.india import guidelines as g
from synera_core.india.cities import City

RANGES: dict[str, tuple[float, float]] = {
    "temperature_c": (-60, 60), "apparent_c": (-70, 80), "humidity_pct": (0, 100), "wind_kmh": (0, 250), "gust_kmh": (0, 350), "wind_dir_deg": (0, 360),
    "precip_mm": (0, 500), "pressure_hpa": (300, 1100), "pm25": (0, 2000), "pm10": (0, 3000), "no2": (0, 2000), "so2": (0, 2000), "o3": (0, 1500),
    "co": (0, 100000), "uv_index": (0, 20), "dust": (0, 5000),
}
UNITS = {"temperature_c": "°C", "apparent_c": "°C", "humidity_pct": "%", "wind_kmh": "km/h", "gust_kmh": "km/h", "wind_dir_deg": "°", "precip_mm": "mm",
         "pressure_hpa": "hPa", "pm25": "µg/m³", "pm10": "µg/m³", "no2": "µg/m³", "so2": "µg/m³", "o3": "µg/m³", "co": "µg/m³", "uv_index": "",
         "dust": "µg/m³", "heat_index_c": "°C"}
LABELS = {"temperature_c": "Temperature", "apparent_c": "Feels like", "humidity_pct": "Relative humidity", "wind_kmh": "Wind speed", "gust_kmh": "Wind gusts",
          "wind_dir_deg": "Wind direction", "precip_mm": "Rainfall (last hour)", "pressure_hpa": "Pressure", "pm25": "PM2.5", "pm10": "PM10", "no2": "NO₂",
          "so2": "SO₂", "o3": "Ozone", "co": "CO", "uv_index": "UV index", "dust": "Dust", "heat_index_c": "Heat index"}
CORE = ("temperature_c", "humidity_pct", "wind_kmh", "pm25", "pm10")      # what the recommendations cannot do without
OM = "Open-Meteo"
CAMS = "Open-Meteo air quality (CAMS model)"

_WEATHER_CURRENT = {"temperature_2m": "temperature_c", "apparent_temperature": "apparent_c", "relative_humidity_2m": "humidity_pct", "wind_speed_10m": "wind_kmh",
                    "wind_gusts_10m": "gust_kmh", "wind_direction_10m": "wind_dir_deg", "precipitation": "precip_mm", "surface_pressure": "pressure_hpa"}
_AIR_CURRENT = {"pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2", "sulphur_dioxide": "so2", "ozone": "o3", "carbon_monoxide": "co", "uv_index": "uv_index",
                "dust": "dust"}


def _num(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _clean(name: str, v: Any, issues: list[str]) -> float | None:
    x = _num(v)
    if x is None:
        return None
    lo, hi = RANGES.get(name, (-math.inf, math.inf))
    if not lo <= x <= hi:
        issues.append(f"{LABELS.get(name, name)} reading {x:g} is outside the physical range {lo:g} to {hi:g} and was discarded")
        return None
    return x


def _metric(name: str, value: float | None, kind: str, source: str, time: str | None) -> dict:
    return {"value": value, "unit": UNITS.get(name, ""), "label": LABELS.get(name, name), "kind": kind, "source": source, "time": time}


def _hourly_frame(w: dict | None, a: dict | None, issues: list[str]) -> pd.DataFrame:
    """Hourly weather and air quality on one time axis (IST, naive)."""
    frames = []
    if w and "hourly" in w:
        h = w["hourly"]
        frames.append(pd.DataFrame({"time": pd.to_datetime(h["time"]), "temperature_c": h.get("temperature_2m"), "humidity_pct": h.get("relative_humidity_2m"),
                                    "apparent_c": h.get("apparent_temperature"), "precip_mm": h.get("precipitation"), "wind_kmh": h.get("wind_speed_10m")}))
    if a and "hourly" in a:
        h = a["hourly"]
        frames.append(pd.DataFrame({"time": pd.to_datetime(h["time"]), "pm25": h.get("pm2_5"), "pm10": h.get("pm10"), "no2": h.get("nitrogen_dioxide"),
                                    "o3": h.get("ozone")}))
    if not frames:
        return pd.DataFrame({"time": pd.to_datetime([])})
    df = frames[0]
    for f in frames[1:]:
        df = df.merge(f, on="time", how="outer")
    df = df.sort_values("time").reset_index(drop=True)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        lo, hi = RANGES[c]
        bad = (df[c] < lo) | (df[c] > hi)
        if bad.any():
            issues.append(f"{int(bad.sum())} hourly {LABELS[c]} values outside the physical range were discarded")
            df.loc[bad, c] = np.nan
    return df


def _trailing_mean(df: pd.DataFrame, col: str, now_i: int, hours: int = 24, need: int = 16) -> float | None:
    """Mean of the last ``hours`` hourly values up to and including ``now_i``; CPCB asks for at least 16 of 24 hours."""
    if col not in df or now_i < 0:
        return None
    seg = df[col].iloc[max(0, now_i - hours + 1): now_i + 1].dropna()
    return float(seg.mean()) if len(seg) >= need else None


def build_reading(city: City, w: dict | None, a: dict | None, station: dict | None = None, fires: dict | None = None,
                  departure_c: float | None = None, sources: list[dict] | None = None) -> dict:
    """One city's validated reading. ``w`` / ``a`` are the Open-Meteo weather and air-quality objects for the city (either may be None)."""
    issues: list[str] = []
    metrics: dict[str, dict] = {}
    t_w = (w or {}).get("current", {}).get("time")
    t_a = (a or {}).get("current", {}).get("time")
    for src, mapping, t, label in ((w, _WEATHER_CURRENT, t_w, OM), (a, _AIR_CURRENT, t_a, CAMS)):
        cur = (src or {}).get("current") or {}
        for raw, name in mapping.items():
            metrics[name] = _metric(name, _clean(name, cur.get(raw), issues), "MODEL_ANALYSIS", label, t)
    df = _hourly_frame(w, a, issues)
    now = pd.Timestamp(t_w or t_a) if (t_w or t_a) else None
    now_i = int(df["time"].searchsorted(now.floor("h"), side="right") - 1) if now is not None and len(df) else -1

    pm25_24, pm10_24 = _trailing_mean(df, "pm25", now_i), _trailing_mean(df, "pm10", now_i)
    aqi_basis = "24-hour average of modelled PM (CAMS), CPCB breakpoints"
    if station and (station.get("pm25") is not None or station.get("pm10") is not None):
        # a CPCB station feed gives 24-hour averages directly; OpenAQ latest values are instantaneous and are only shown, not used for the index
        if station.get("source") == "CPCB":
            pm25_24, pm10_24 = station.get("pm25"), station.get("pm10")
            aqi_basis = f"CPCB station 24-hour averages (median of {station.get('stations')} stations), CPCB breakpoints"
        for nm in ("pm25", "pm10"):
            if station.get(nm) is not None and _clean(nm, station[nm], issues) is not None:
                metrics[f"{nm}_station"] = _metric(nm, station[nm], "OBSERVATION", station["source_label"], station.get("time"))
                metrics[f"{nm}_station"]["label"] = f"{LABELS[nm]} (station)"
    aqi = g.national_aqi(pm25_24, pm10_24)
    aqi["basis"] = aqi_basis
    aqi["kind"] = "OBSERVATION" if station and station.get("source") == "CPCB" and aqi["index"] is not None else "DERIVED"
    aqi["pm25_24h"], aqi["pm10_24h"] = pm25_24, pm10_24
    aqi["note"] = "PM-based index: CPCB's official figure also needs NO2, SO2, O3, CO, NH3 and Pb sub-indices, which are not available here." if aqi["index"] is not None else None

    # heat
    t, rh = metrics["temperature_c"]["value"], metrics["humidity_pct"]["value"]
    hi = float(calculate_heat_index(pd.Series([t]), pd.Series([rh])).iloc[0]) if t is not None and rh is not None else None
    daily = _daily(w, now)
    today = next((d for d in daily if d["is_today"]), None)
    # heat stress for today is the larger of the heat index now and today's forecast peak apparent temperature (the same quantity the engine's heat input uses),
    # so an evening or night reading does not hide the day's worst
    peak = today["apparent_max_c"] if today else None
    stress = max((x for x in (hi, peak) if x is not None), default=None)
    hi_cat = g.heat_index_category(stress)
    tmax = today["tmax_c"] if today else None
    imd = g.imd_heat(tmax, departure_c, city["terrain"])
    # rain
    rain24 = None
    if len(df) and now_i >= 0 and "precip_mm" in df and df["precip_mm"].iloc[max(0, now_i - 23): now_i + 1].notna().sum() >= 20:
        rain24 = float(df["precip_mm"].iloc[max(0, now_i - 23): now_i + 1].sum())
    rain_next = max((d["precip_mm"] or 0.0 for d in daily if d["is_future"]), default=None) if any(d["is_future"] for d in daily) else None
    rain_cat = g.imd_rain(rain24)
    rain_next_cat = g.imd_rain(rain_next)
    uv_max = today["uv_max"] if today else None
    comp = g.composite_risk(aqi["level"], hi_cat[1] if hi_cat else None, max(c[1] for c in (rain_cat, rain_next_cat) if c) if (rain_cat or rain_next_cat) else None)

    missing = [n for n in CORE if metrics.get(n, {}).get("value") is None] + (["aqi"] if aqi["index"] is None else [])
    quality = {"issues": issues, "missing": missing, "completeness": round(1 - len(missing) / (len(CORE) + 1), 2)}
    series = None
    if len(df):
        d2 = df.copy()
        d2["pm25_24h"] = d2["pm25"].rolling(24, min_periods=16).mean() if "pm25" in d2 else np.nan
        d2["pm10_24h"] = d2["pm10"].rolling(24, min_periods=16).mean() if "pm10" in d2 else np.nan
        d2["aqi"] = [g.national_aqi(None if pd.isna(p) else p, None if pd.isna(q) else q)["index"] for p, q in zip(d2["pm25_24h"], d2["pm10_24h"])]
        lo, hi_i = max(0, now_i - 71), min(len(d2), now_i + 73)
        seg = d2.iloc[lo:hi_i]
        series = {"time": [x.strftime("%Y-%m-%dT%H:%M") for x in seg["time"]], "now_index": now_i - lo,
                  **{c: [None if pd.isna(v) else round(float(v), 2) for v in seg[c]] for c in ("temperature_c", "humidity_pct", "apparent_c", "precip_mm", "wind_kmh", "pm25", "pm10", "aqi") if c in seg},
                  "observed_until": (now.floor("h").strftime("%Y-%m-%dT%H:%M") if now is not None else None)}
    return {
        "city": {k: city[k] for k in ("id", "name", "state", "lat", "lon", "terrain")},
        "as_of": t_w or t_a, "timezone": "Asia/Kolkata (IST)", "metrics": metrics,
        "derived": {"aqi": aqi, "heat_index_c": hi, "heat_peak_c": peak, "heat_stress_c": stress, "heat_index": {"category": hi_cat[0], "level": hi_cat[1]} if hi_cat else None,
                    "imd_heat": {**imd, "tmax_c": tmax, "departure_c": departure_c}, "rain_24h_mm": rain24, "rain": {"category": rain_cat[0], "level": rain_cat[1]} if rain_cat else None,
                    "rain_next_days_max_mm": rain_next, "rain_next": {"category": rain_next_cat[0], "level": rain_next_cat[1]} if rain_next_cat else None,
                    "uv_max": uv_max, "uv": ({"category": g.uv_category(uv_max)[0], "level": g.uv_category(uv_max)[1]} if uv_max is not None else None), "composite": comp},
        "series": series, "daily": daily, "fires": fires, "quality": quality, "sources": sources or [],
    }


def _daily(w: dict | None, now: pd.Timestamp | None) -> list[dict]:
    d = (w or {}).get("daily")
    if not d or now is None:
        return []
    today = now.strftime("%Y-%m-%d")
    out = []
    for i, day in enumerate(d["time"]):
        out.append({"date": day, "is_today": day == today, "is_future": day > today, "tmax_c": _num(d["temperature_2m_max"][i]), "tmin_c": _num(d["temperature_2m_min"][i]),
                    "apparent_max_c": _num(d["apparent_temperature_max"][i]), "precip_mm": _num(d["precipitation_sum"][i]), "uv_max": _num(d["uv_index_max"][i]),
                    "wind_max_kmh": _num(d["wind_speed_10m_max"][i]), "kind": "FORECAST" if day > today else "MODEL_ANALYSIS"})
    return out


def map_summary(r: dict) -> dict:
    """The small record the map needs per city (one line per marker)."""
    m, d = r["metrics"], r["derived"]
    return {"id": r["city"]["id"], "name": r["city"]["name"], "state": r["city"]["state"], "lat": r["city"]["lat"], "lon": r["city"]["lon"],
            "temperature_c": m["temperature_c"]["value"], "humidity_pct": m["humidity_pct"]["value"], "wind_kmh": m["wind_kmh"]["value"],
            "wind_dir_deg": m["wind_dir_deg"]["value"], "rain_24h_mm": d["rain_24h_mm"], "rain_next_mm": d["rain_next_days_max_mm"], "pm25": m["pm25"]["value"], "pm10": m["pm10"]["value"],
            "aqi": d["aqi"]["index"], "aqi_category": d["aqi"]["category"], "aqi_level": d["aqi"]["level"], "heat_index_c": d["heat_stress_c"],
            "heat_category": (d["heat_index"] or {}).get("category"), "heat_level": (d["heat_index"] or {}).get("level"), "imd_heat": d["imd_heat"]["status"],
            "risk": d["composite"]["score"], "risk_tier": d["composite"]["tier"], "risk_driver": d["composite"]["driver"], "completeness": r["quality"]["completeness"]}
