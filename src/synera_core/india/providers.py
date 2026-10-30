"""Live data providers for the India map: Open-Meteo (weather, modelled air quality), and, when a key is configured, OpenAQ, CPCB (data.gov.in)
and NASA FIRMS. Every call goes through :func:`_get` (retries, honours 429 / Retry-After) and a TTL cache that falls back to the last good copy,
marked ``stale``, when a provider is down. Nothing is ever invented: a failed provider yields ``None`` and a reason.

Environment variables (all optional; without a key that provider simply reports ``NOT_CONFIGURED``):

* ``OPENAQ_API_KEY``      OpenAQ v3 station observations (https://docs.openaq.org)
* ``DATA_GOV_IN_API_KEY`` CPCB real-time air-quality feed on data.gov.in (https://data.gov.in)
* ``FIRMS_MAP_KEY``       NASA FIRMS active-fire detections (https://firms.modaps.eosdis.nasa.gov/api/map_key)
* ``SYNERA_OFFLINE=1``    never call out; serve cached copies only
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import numpy as np
import pandas as pd

from synera_core.config import find_repo_root
from synera_core.india.cities import City

UA = {"User-Agent": "SYNERA/1.0 (environmental research; contact via repository)"}
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CHUNK = 25                       # locations per Open-Meteo request
TTL_LIVE_S = 15 * 60             # Open-Meteo refreshes its current values every 15 minutes
TTL_STATION_S = 30 * 60
TTL_CLIM_S = 30 * 24 * 3600
CLIM_YEARS = (2023, 2025)        # three full years of the same calendar window

WEATHER_CURRENT = "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
WEATHER_HOURLY = "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m"
WEATHER_DAILY = "temperature_2m_max,temperature_2m_min,apparent_temperature_max,precipitation_sum,uv_index_max,wind_speed_10m_max"
AIR_CURRENT = "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi,uv_index,dust,aerosol_optical_depth"
AIR_HOURLY = "pm2_5,pm10,nitrogen_dioxide,ozone,us_aqi"


class SourceError(RuntimeError):
    """A provider could not be read (after retries). The message is safe to show."""


def offline() -> bool:
    return os.environ.get("SYNERA_OFFLINE", "0") == "1"


def cache_dir() -> Path:
    d = find_repo_root() / "artifacts" / "cache" / "india"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str, params: dict | None = None, headers: dict | None = None, tries: int = 3, timeout: float = 30.0, text: bool = False) -> Any:
    """GET with retries. 429 waits for Retry-After (capped), 5xx and network errors back off; 4xx other than 429 fails at once."""
    last = "no attempt made"
    for attempt in range(tries):
        try:
            r = httpx.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
            if r.status_code == 429:
                wait = min(float(r.headers.get("Retry-After", 2 ** attempt)), 10.0)
                last = "rate limited (HTTP 429)"
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                last = f"server error (HTTP {r.status_code})"
                time.sleep(0.6 * (2 ** attempt))
                continue
            if r.status_code >= 400:
                raise SourceError(f"HTTP {r.status_code}: {r.text[:160]}")
            return r.text if text else r.json()
        except httpx.HTTPError as exc:
            last = f"network error: {type(exc).__name__}"
            time.sleep(0.6 * (2 ** attempt))
    raise SourceError(last)


_mem: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl: float, loader: Callable[[], Any]) -> tuple[Any, dict]:
    """(value, meta). meta.status is ``live`` (just fetched), ``cached`` (within ttl), or ``stale`` (provider failed; last good copy) -
    or the SourceError propagates when there is nothing at all to show."""
    now = time.time()
    hit = _mem.get(key)
    path = cache_dir() / (key.replace("/", "_").replace(":", "_") + ".json")
    if hit is None and path.exists():
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
            hit = (blob["ts"], blob["value"])
            _mem[key] = hit
        except (OSError, ValueError, KeyError):
            hit = None
    if hit and (offline() or now - hit[0] < ttl):
        return hit[1], {"status": "cached", "fetched_at": hit[0]}
    if offline():
        raise SourceError("offline mode and nothing cached")
    try:
        value = loader()
    except SourceError as exc:
        if hit:
            return hit[1], {"status": "stale", "fetched_at": hit[0], "note": f"live fetch failed ({exc}); showing the last good copy"}
        raise
    _mem[key] = (now, value)
    try:
        path.write_text(json.dumps({"ts": now, "value": value}), encoding="utf-8")
    except OSError:
        pass
    return value, {"status": "live", "fetched_at": now}


# ---- Open-Meteo ---------------------------------------------------------------------------------------------------------
def _as_list(j: Any) -> list[dict]:
    return j if isinstance(j, list) else [j]


def _openmeteo(url: str, cities: list[City], extra: dict) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(cities), CHUNK):
        part = cities[i:i + CHUNK]
        params = {"latitude": ",".join(f"{c['lat']}" for c in part), "longitude": ",".join(f"{c['lon']}" for c in part),
                  "timezone": "Asia/Kolkata", **extra}
        res = _as_list(_get(url, params))
        if len(res) != len(part):
            raise SourceError(f"Open-Meteo returned {len(res)} locations for {len(part)} requested")
        out.extend(res)
    return out


def _key(prefix: str, cities: list[City]) -> str:
    ids = "-".join(c["id"] for c in cities)
    return f"{prefix}_{ids}" if len(cities) <= 3 else f"{prefix}_{len(cities)}_{hashlib.sha1(ids.encode()).hexdigest()[:10]}"


def weather(cities: list[City]) -> tuple[list[dict], dict]:
    return cached(_key("om_weather", cities), TTL_LIVE_S, lambda: _openmeteo(WEATHER_URL, cities, {
        "current": WEATHER_CURRENT, "hourly": WEATHER_HOURLY, "daily": WEATHER_DAILY, "past_days": 7, "forecast_days": 4, "wind_speed_unit": "kmh"}))


def air(cities: list[City]) -> tuple[list[dict], dict]:
    return cached(_key("om_air", cities), TTL_LIVE_S, lambda: _openmeteo(AIR_URL, cities, {"current": AIR_CURRENT, "hourly": AIR_HOURLY, "past_days": 7, "forecast_days": 4}))


# ---- climatology (the city's own normal for this time of year) ----------------------------------------------------------
def _daily_series(city: City) -> dict:
    a, b = f"{CLIM_YEARS[0]}-01-01", f"{CLIM_YEARS[1]}-12-31"
    base = {"latitude": city["lat"], "longitude": city["lon"], "start_date": a, "end_date": b, "timezone": "Asia/Kolkata"}
    w = _get(ARCHIVE_URL, {**base, "wind_speed_unit": "kmh",
                           "daily": "apparent_temperature_max,temperature_2m_max,relative_humidity_2m_mean,precipitation_sum,wind_speed_10m_max"}, timeout=60)["daily"]
    h = _get(AIR_URL, {**base, "hourly": "pm2_5,pm10,ozone,nitrogen_dioxide"}, timeout=90)["hourly"]
    ah = pd.DataFrame(h)
    ah["date"] = pd.to_datetime(ah["time"]).dt.strftime("%Y-%m-%d")
    ad = ah.drop(columns=["time"]).groupby("date").mean().reset_index()
    wd = pd.DataFrame(w).rename(columns={"time": "date"})
    d = wd.merge(ad, on="date", how="left")
    return {c: [None if pd.isna(v) else float(v) if c != "date" else v for v in d[c]] for c in d.columns}


def daily_history(city: City) -> dict | None:
    try:
        return cached(f"om_clim_{city['id']}", TTL_CLIM_S, lambda: _daily_series(city))[0]
    except SourceError:
        return None


# ---- optional providers --------------------------------------------------------------------------------------------------
def openaq_latest(city: City, radius_m: int = 25000) -> tuple[dict | None, dict]:
    """Latest PM2.5/PM10 from OpenAQ stations within ``radius_m`` of the city (median across stations that reported in the last 3 hours).
    OpenAQ v3 API: GET /v3/locations?coordinates=lat,lon&radius=..., then GET /v3/locations/{id}/latest."""
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        return None, {"status": "NOT_CONFIGURED", "note": "set OPENAQ_API_KEY to add station observations"}

    def load() -> dict:
        h = {"X-API-Key": key}
        locs = _get("https://api.openaq.org/v3/locations", {"coordinates": f"{city['lat']},{city['lon']}", "radius": radius_m, "limit": 20}, h)["results"]
        names: dict[int, str] = {}
        for loc in locs:
            for s in loc.get("sensors", []):
                nm = (s.get("parameter") or {}).get("name")
                if nm in ("pm25", "pm10"):
                    names[s["id"]] = nm
        vals: dict[str, list[float]] = {"pm25": [], "pm10": []}
        stamps: list[str] = []
        for loc in locs[:8]:
            for r in _get(f"https://api.openaq.org/v3/locations/{loc['id']}/latest", None, h).get("results", []):
                nm = names.get(r.get("sensorsId"))
                utc = (r.get("datetime") or {}).get("utc")
                if nm and utc and r.get("value") is not None and r["value"] >= 0:
                    if time.time() - pd.Timestamp(utc).timestamp() < 3 * 3600:
                        vals[nm].append(float(r["value"]))
                        stamps.append(utc)
        return {"pm25": float(np.median(vals["pm25"])) if vals["pm25"] else None, "pm10": float(np.median(vals["pm10"])) if vals["pm10"] else None,
                "stations": len({*stamps}), "n_pm25": len(vals["pm25"]), "n_pm10": len(vals["pm10"]), "latest_utc": max(stamps) if stamps else None}

    try:
        v, meta = cached(f"openaq_{city['id']}", TTL_STATION_S, load)
        return (v if (v["pm25"] is not None or v["pm10"] is not None) else None), meta
    except SourceError as exc:
        return None, {"status": "ERROR", "note": str(exc)}


def cpcb_latest(city: City) -> tuple[dict | None, dict]:
    """CPCB real-time station feed on data.gov.in (resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69): per-station pollutant averages.
    Returns the median station PM2.5 / PM10 average for the city name."""
    key = os.environ.get("DATA_GOV_IN_API_KEY")
    if not key:
        return None, {"status": "NOT_CONFIGURED", "note": "set DATA_GOV_IN_API_KEY to add CPCB station averages"}

    def load() -> dict:
        j = _get("https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69",
                 {"api-key": key, "format": "json", "limit": 500, "filters[city]": city["name"]})
        vals: dict[str, list[float]] = {"PM2.5": [], "PM10": []}
        stations, last = set(), []
        for r in j.get("records", []):
            p = r.get("pollutant_id") or r.get("pollutant")
            try:
                v = float(r.get("pollutant_avg"))
            except (TypeError, ValueError):
                continue
            if p in vals and v >= 0:
                vals[p].append(v)
                stations.add(r.get("station"))
                last.append(r.get("last_update") or "")
        return {"pm25": float(np.median(vals["PM2.5"])) if vals["PM2.5"] else None, "pm10": float(np.median(vals["PM10"])) if vals["PM10"] else None,
                "stations": len(stations), "last_update": max(last) if last else None}

    try:
        v, meta = cached(f"cpcb_{city['id']}", TTL_STATION_S, load)
        return (v if (v["pm25"] is not None or v["pm10"] is not None) else None), meta
    except SourceError as exc:
        return None, {"status": "ERROR", "note": str(exc)}


def firms_fires(city: City, half_width_deg: float = 0.75, days: int = 2) -> tuple[dict | None, dict]:
    """Active-fire detections (VIIRS SNPP NRT) in a box around the city over the last ``days`` days. Satellite detections, not confirmed fires."""
    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        return None, {"status": "NOT_CONFIGURED", "note": "set FIRMS_MAP_KEY to add satellite fire detections"}

    def load() -> dict:
        w, s, e, n = city["lon"] - half_width_deg, city["lat"] - half_width_deg, city["lon"] + half_width_deg, city["lat"] + half_width_deg
        txt = _get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{w:.3f},{s:.3f},{e:.3f},{n:.3f}/{days}", text=True)
        if not txt.strip() or txt.lower().startswith(("invalid", "error")):
            raise SourceError(txt.strip()[:120] or "empty FIRMS reply")
        df = pd.read_csv(io.StringIO(txt))
        conf = df["confidence"].astype(str).str.lower() if "confidence" in df else pd.Series([], dtype=str)
        return {"count": int(len(df)), "high_confidence": int(conf.isin(["h", "high"]).sum()), "days": days, "box_deg": half_width_deg * 2,
                "latest": f"{df['acq_date'].max()} {int(df['acq_time'].max()):04d} UTC" if len(df) else None}

    try:
        return cached(f"firms_{city['id']}", TTL_STATION_S, load)
    except SourceError as exc:
        return None, {"status": "ERROR", "note": str(exc)}
