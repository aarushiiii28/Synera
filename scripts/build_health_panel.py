"""Build the REAL health-outcome panel (Track C): weekly all-cause deaths per US state joined to the weather and air
pollution each state experienced, 2014-2019 (before COVID-19, which would swamp everything).

    python scripts/build_health_panel.py          # downloads once (cached under data/raw/health), then offline

Sources (all public):
  * deaths   CDC NCHS "Weekly Counts of Deaths by State and Select Causes, 2014-2019" (data.cdc.gov, dataset 3yf8-kanr)
  * air      US EPA Air Quality System daily summaries (aqs.epa.gov/aqsweb/airdata): PM2.5, PM10, ozone, NO2
  * weather  Open-Meteo historical archive (ERA5 reanalysis), CC BY 4.0, at each state's largest metro area

Output: data/processed/us_mortality_panel.parquet  (city = state, date = week ending Saturday, the ten engine stressors in
physical units, ``outcome`` = excess all-cause mortality in % vs the state's own expected trend and season) and a QC json.
Nothing is imputed: a state-week is kept only if every stressor and the death count are measured.
"""
from __future__ import annotations

import json
import sys
import time
import zipfile

import httpx
import pandas as pd

from synera_core.config import find_repo_root
from synera_core.data.health import LOCATIONS, excess_mortality, national_week_adjust
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger

ROOT = find_repo_root()
RAW = ROOT / "data" / "raw" / "health"
OUT = ROOT / "data" / "processed" / "us_mortality_panel.parquet"
QC = ROOT / "data" / "processed" / "us_mortality_panel_qc.json"
YEARS = range(2014, 2020)
MIN_WEEKS = 150          # a state needs about three years of complete weeks to estimate its own normal and baseline

# EPA parameter code -> (stressor, daily column, conversion to the stressor's unit)
AIR = {"88101": ("pm25", "Arithmetic Mean", 1.0),            # ug/m3
       "81102": ("pm10", "Arithmetic Mean", 1.0),            # ug/m3
       "44201": ("o3", "1st Max Value", 1960.0),             # daily max 8-hour average, ppm -> ug/m3 (1 ppb ~ 1.96 ug/m3)
       "42602": ("no2", "Arithmetic Mean", 1.88)}            # ppb -> ug/m3 (1 ppb ~ 1.88 ug/m3)
WEATHER_VARS = "apparent_temperature_max,relative_humidity_2m_mean,precipitation_sum,wind_speed_10m_max"


def log(msg: str) -> None:
    print(msg, flush=True)


# ------------------------------------------------------------------------------------------------ deaths
def load_deaths() -> pd.DataFrame:
    cache = RAW / "cdc_weekly_deaths_2014_2019.json"
    if not cache.exists():
        log("  downloading CDC weekly deaths ...")
        r = httpx.get("https://data.cdc.gov/resource/3yf8-kanr.json", params={"$limit": 100000}, timeout=120)
        r.raise_for_status()
        cache.write_text(r.text, encoding="utf-8")
    d = pd.DataFrame(json.loads(cache.read_text(encoding="utf-8")))
    d = d.rename(columns={"jurisdiction_of_occurrence": "city", "allcause": "deaths_all", "diseases_of_heart_i00_i09": "deaths_heart",
                          "chronic_lower_respiratory": "deaths_resp", "cerebrovascular_diseases": "deaths_cerebro"})
    d["date"] = pd.to_datetime(d["weekendingdate"]).dt.normalize()
    for c in ("deaths_all", "deaths_heart", "deaths_resp", "deaths_cerebro"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["city"].isin(LOCATIONS)]
    return d[["city", "date", "deaths_all", "deaths_heart", "deaths_resp", "deaths_cerebro"]].sort_values(["city", "date"]).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ air (EPA)
def load_air() -> pd.DataFrame:
    """State x day means of each pollutant across all monitors, from the EPA daily summary files."""
    cache = RAW / "epa_state_daily.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    frames = []
    for code, (name, col, mult) in AIR.items():
        for year in YEARS:
            zp = RAW / "epa" / f"daily_{code}_{year}.zip"
            if not zp.exists():
                zp.parent.mkdir(parents=True, exist_ok=True)
                log(f"  downloading EPA {name} {year} ...")
                r = httpx.get(f"https://aqs.epa.gov/aqsweb/airdata/daily_{code}_{year}.zip", timeout=300, follow_redirects=True)
                r.raise_for_status()
                zp.write_bytes(r.content)
            with zipfile.ZipFile(zp) as z:
                with z.open(z.namelist()[0]) as f:
                    d = pd.read_csv(f, usecols=["State Name", "Date Local", col], dtype={"State Name": str})
            d = d.dropna(subset=[col])
            g = d.groupby(["State Name", "Date Local"])[col].mean().mul(mult).rename(name).reset_index()
            frames.append(g.assign(_p=name))
    out = {}
    for name in [v[0] for v in AIR.values()]:
        part = pd.concat([f.drop(columns="_p") for f in frames if f["_p"].iloc[0] == name])
        out[name] = part.set_index(["State Name", "Date Local"])[name]
    air = pd.concat(out.values(), axis=1).reset_index().rename(columns={"State Name": "city", "Date Local": "date"})
    air["date"] = pd.to_datetime(air["date"])
    air.to_parquet(cache, index=False)
    return air


# ------------------------------------------------------------------------------------------------ weather (Open-Meteo)
def load_weather(state: str) -> pd.DataFrame:
    cache = RAW / "openmeteo" / f"{state.replace(' ', '_')}.json"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        lat, lon = LOCATIONS[state]
        last = "no response"
        for attempt in range(8):
            try:
                r = httpx.get("https://archive-api.open-meteo.com/v1/archive", timeout=120, params={
                    "latitude": lat, "longitude": lon, "start_date": "2013-10-01", "end_date": "2019-12-31", "timezone": "auto",
                    "daily": WEATHER_VARS})
                if r.status_code == 200:
                    cache.write_text(r.text, encoding="utf-8")
                    break
                last = f"HTTP {r.status_code} {r.text[:100]}"
            except httpx.HTTPError as exc:     # connection reset, timeout: the free API throttles bursts
                last = f"{type(exc).__name__}: {exc}"
            time.sleep(8 * (attempt + 1))
        else:
            raise RuntimeError(f"Open-Meteo failed for {state}: {last}")
        time.sleep(2.0)
    j = json.loads(cache.read_text(encoding="utf-8"))["daily"]
    d = pd.DataFrame(j).rename(columns={"time": "date", "apparent_temperature_max": "heat_index", "relative_humidity_2m_mean": "rh",
                                        "precipitation_sum": "precip", "wind_speed_10m_max": "wind"})
    d["date"] = pd.to_datetime(d["date"])
    d = d[["date", "heat_index", "rh", "precip", "wind"]].set_index("date").astype(float)
    d["uv"] = load_uv(state).reindex(d.index)
    # drought index: 30-day rainfall total as a z-score against the state's own climatology for that calendar month
    # (sign flipped so that higher = drier, matching the other panels)
    r30 = d["precip"].rolling(30, min_periods=25).sum()
    month = r30.index.month
    z = (r30 - r30.groupby(month).transform("mean")) / r30.groupby(month).transform("std")
    d["drought_index"] = -z
    return d


def load_uv(state: str) -> pd.Series:
    """Daily all-sky surface UV index from NASA POWER (the Open-Meteo archive has no UV for these years)."""
    cache = RAW / "nasa_power" / f"{state.replace(' ', '_')}.json"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        lat, lon = LOCATIONS[state]
        last = "no response"
        for attempt in range(8):
            try:
                r = httpx.get("https://power.larc.nasa.gov/api/temporal/daily/point", timeout=120, params={
                    "parameters": "ALLSKY_SFC_UV_INDEX", "community": "RE", "longitude": lon, "latitude": lat,
                    "start": "20131001", "end": "20191231", "format": "JSON"})
                if r.status_code == 200:
                    cache.write_text(r.text, encoding="utf-8")
                    break
                last = f"HTTP {r.status_code} {r.text[:100]}"
            except httpx.HTTPError as exc:
                last = f"{type(exc).__name__}: {exc}"
            time.sleep(8 * (attempt + 1))
        else:
            raise RuntimeError(f"NASA POWER failed for {state}: {last}")
        time.sleep(1.0)
    vals = json.loads(cache.read_text(encoding="utf-8"))["properties"]["parameter"]["ALLSKY_SFC_UV_INDEX"]
    s = pd.Series(vals, dtype=float)
    s.index = pd.to_datetime(s.index, format="%Y%m%d")
    return s.where(s > -900)           # -999 is NASA's missing-value flag

def weekly(daily: pd.DataFrame, min_days: int) -> pd.DataFrame:
    """Mean over the 7 days ending on each Saturday (the CDC week), needing at least ``min_days`` valid days."""
    return daily.resample("W-SAT", label="right", closed="right").mean().where(
        daily.notna().resample("W-SAT", label="right", closed="right").sum() >= min_days)


CAUSES = {"heart": ("deaths_heart", "us_heart_panel.parquet"), "stroke": ("deaths_cerebro", "us_stroke_panel.parquet")}


def cause_panel(full: pd.DataFrame, stress: list[str], col: str) -> pd.DataFrame:
    """The same panel with one cause of death as the outcome (weeks where the CDC suppressed a count below 10 are left out)."""
    rows = []
    for _, g in full.groupby("city"):
        g = g[g[col].notna() & (g[col] >= 10)].sort_values("date")
        if len(g) < MIN_WEEKS:
            continue
        e, ex = excess_mortality(g["date"], g[col])
        rows.append(g.assign(outcome_raw=e, expected=ex))
    d = pd.concat(rows).dropna(subset=stress)
    per = d.groupby("city").size()
    d = d[d["city"].isin(per[per >= MIN_WEEKS].index)].sort_values(["city", "date"]).reset_index(drop=True)
    d["outcome"] = national_week_adjust(d["date"], d["outcome_raw"].to_numpy(), d["expected"].to_numpy())
    return d[["city", "date", *stress, "outcome", "outcome_raw", "deaths_all", "deaths_heart", "deaths_resp", "deaths_cerebro", "expected"]]

def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    log("1. deaths (CDC NCHS)")
    deaths = load_deaths()
    log(f"   {deaths['city'].nunique()} states, {deaths['date'].min():%Y-%m-%d}..{deaths['date'].max():%Y-%m-%d}, {len(deaths)} state-weeks")
    log("2. air pollution (EPA AQS monitors)")
    air = load_air()
    log("3. weather (Open-Meteo)")
    rows = []
    for i, state in enumerate(sorted(LOCATIONS), 1):
        wd = load_weather(state)
        w = weekly(wd[["heat_index", "rh", "precip", "wind", "uv", "drought_index"]], 6)
        # the drought index is a state of the last 30 days: take its value at the end of the week
        w["drought_index"] = wd["drought_index"].resample("W-SAT", label="right", closed="right").last()
        a = air[air["city"] == state].set_index("date")[["pm25", "pm10", "o3", "no2"]]
        a = a.reindex(pd.date_range("2013-12-29", "2019-12-31", freq="D"))
        aw = weekly(a, 1)      # many states sample particles only 1 day in 3 or 6: average the days actually measured that week
        dsub = deaths[deaths["city"] == state].set_index("date")
        j = dsub.join(w, how="left").join(aw, how="left")
        j["city"] = state
        j["excess"], j["expected"] = excess_mortality(pd.Series(j.index, index=j.index), j["deaths_all"].ffill().bfill())
        rows.append(j.reset_index())
        if i % 10 == 0:
            log(f"   {i}/{len(LOCATIONS)} states")
    full = pd.concat(rows, ignore_index=True)
    stress = ["heat_index", "pm25", "rh", "o3", "drought_index", "pm10", "no2", "uv", "wind", "precip"]

    cover = {s: float(1 - full[s].isna().mean()) for s in stress}
    keep = full.dropna(subset=[*stress, "deaths_all"]).copy()
    keep = keep.rename(columns={"excess": "outcome_raw"})
    keep = keep[["city", "date", *stress, "outcome_raw", "deaths_all", "deaths_heart", "deaths_resp", "deaths_cerebro", "expected"]]
    per_state = keep.groupby("city").size()
    dropped = {k: int(v) for k, v in per_state[per_state < MIN_WEEKS].items()}
    keep = keep[keep["city"].isin(per_state[per_state >= MIN_WEEKS].index)]
    if dropped:
        log(f"   dropped states with fewer than {MIN_WEEKS} complete weeks: {dropped}")
    keep = keep.sort_values(["city", "date"]).reset_index(drop=True)
    keep["date"] = pd.to_datetime(keep["date"])
    # remove what hits the whole country in a week (flu waves, nationwide heat or cold), so only differences between states remain
    keep["outcome"] = national_week_adjust(keep["date"], keep["outcome_raw"].to_numpy(), keep["expected"].to_numpy())
    keep = keep[["city", "date", *stress, "outcome", "outcome_raw", "deaths_all", "deaths_heart", "deaths_resp", "deaths_cerebro", "expected"]]
    log(f"4. panel: {len(full)} state-weeks -> {len(keep)} complete ({len(keep) / len(full):.0%}) in {keep['city'].nunique()} states")
    for s in stress:
        log(f"   {s:14s} available in {cover[s]:5.1%} of state-weeks")
    if len(keep) < 2000 or keep["city"].nunique() < 10:
        log("   too little complete data; not writing the panel")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    keep.to_parquet(OUT, index=False)
    qc = {
        "title": "US weekly all-cause mortality joined to weather and air pollution, 2014-2019",
        "provenance": "REAL", "rows": int(len(keep)), "states": int(keep["city"].nunique()),
        "date_start": str(keep["date"].min().date()), "date_end": str(keep["date"].max().date()),
        "coverage_of_state_weeks": cover, "complete_state_weeks": float(len(keep) / len(full)), "states_dropped_for_too_few_complete_weeks": dropped,
        "sources": {
            "deaths": "CDC NCHS Weekly Counts of Deaths by State and Select Causes, 2014-2019 (data.cdc.gov 3yf8-kanr), public domain",
            "air": "US EPA Air Quality System daily summary files (aqs.epa.gov/aqsweb/airdata), public domain",
            "weather": "Open-Meteo historical archive (ERA5), CC BY 4.0, https://open-meteo.com",
            "uv": "NASA POWER all-sky surface UV index (ALLSKY_SFC_UV_INDEX), daily, public domain"},
        "outcome": "excess all-cause mortality in %: 100 x (log weekly deaths - the state's own fitted trend and 3 annual harmonics), minus the death-weighted average of all states in the same week (removes nationwide flu waves and weather); outcome_raw keeps the version without that subtraction",
        "limitations": [
            "Exposure is one metro area's weather and the state's mean monitor reading, so it is only a proxy for what the state's people breathed; this blurs real effects toward zero.",
            "Weekly state totals hide the day-level heat response; effects are weekly and ecological, not individual.",
            "Many states run particle and NO2 monitors only 1 day in 3 or 6, so a week's value averages only the days measured: noisier, which also blurs real effects toward zero.",
            "New York is excluded (CDC splits New York City from the rest of the state; monitors cannot be split the same way)."],
    }
    QC.write_text(json.dumps(qc, indent=2), encoding="utf-8")
    extra = []
    for name, (col, fname) in CAUSES.items():
        cp = cause_panel(full, stress, col)
        path = OUT.with_name(fname)
        cp.to_parquet(path, index=False)
        extra.append(path)
        log(f"   {name}: {len(cp)} state-weeks in {cp['city'].nunique()} states -> {fname}")
    ledger = open_ledger()
    manifest = ROOT / "data" / "MANIFEST.json"
    for p in (OUT, QC, *extra):
        register_file(ledger, p, "dataset", {"provenance": "REAL", "description": "US weekly mortality x weather x air pollution (Track C)"}, manifest_path=manifest)
    log(f"   wrote {OUT.name} ({OUT.stat().st_size / 1e6:.2f} MB); registered in the ledger")
    return 0


if __name__ == "__main__":
    sys.exit(main())
