"""Build the LATER-DATA replication panels for Track D: the same Indian states, the same outcome construction, but only days AFTER the analysis window.

    python scripts/build_india_grid_late.py        # downloads once (cached under data/raw/india_grid_late), then offline

The discovery panels (``build_india_grid_panel.py``) end on 2024-04-28. The panels built here start on 2024-04-29, so not one of their days was used to find
a pair. They are the data a finding must survive to count as replicated on later data (check G7).

Sources, both public:
  demand   Robbie Andrew's daily compilation of Grid-India (POSOCO) state reports, https://robbieandrew.github.io/india/ (EnergyMet per state). Over the days it shares
           with the Zenodo record used for discovery the two agree almost exactly: it is the same operator's numbers, separately compiled, so what is new is time,
           not the reporting system.
  weather  Open-Meteo historical archive (ERA5), CC BY 4.0, averaged over 3 large cities per state (1 for Delhi). This is built differently from the state averages
           in the discovery panels, so the check is not a copy of the original inputs.

Outputs india_grid_late_panel.parquet (the 8 states of india_grid) and india_grid_b_late_panel.parquet (the 8 states of india_grid_b), each with a QC json.
"""
from __future__ import annotations

import json
import sys
import time

import httpx
import numpy as np
import pandas as pd

from synera_core.config import find_repo_root
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger

sys.path.insert(0, str(find_repo_root() / "scripts"))
from build_india_grid_panel import GROUPS, STRESS, expected_log   # noqa: E402  (same outcome construction as discovery)

ROOT = find_repo_root()
RAW = ROOT / "data" / "raw" / "india_grid_late"
PROC = ROOT / "data" / "processed"
DEMAND_URL = "https://robbieandrew.github.io/india/data/POSOCO_data.csv"
START, END = "2024-04-29", "2026-10-15"
MIN_DAYS = 500
DEMAND_COL = {"Madhya Pradesh": "MP", "Uttar Pradesh": "UP"}          # state names that differ in the compilation
CITIES = {
    "Maharashtra": [(19.08, 72.88), (18.52, 73.86), (21.15, 79.09)], "Gujarat": [(23.02, 72.57), (21.17, 72.83), (22.30, 70.80)],
    "Uttar Pradesh": [(26.85, 80.95), (26.45, 80.33), (25.32, 83.01)], "Tamil Nadu": [(13.08, 80.27), (11.02, 76.96), (9.92, 78.12)],
    "Rajasthan": [(26.91, 75.79), (26.24, 73.02), (25.18, 75.84)], "Karnataka": [(12.97, 77.59), (12.30, 76.64), (15.36, 75.12)],
    "Delhi": [(28.61, 77.21)], "Punjab": [(30.90, 75.85), (31.63, 74.87), (30.34, 76.39)],
    "Madhya Pradesh": [(22.72, 75.86), (23.26, 77.41), (23.18, 79.99)], "Andhra Pradesh": [(17.69, 83.22), (16.51, 80.65), (13.63, 79.42)],
    "Telangana": [(17.39, 78.49), (17.97, 79.59), (18.67, 78.09)], "West Bengal": [(22.57, 88.36), (23.68, 86.98), (26.73, 88.40)],
    "Odisha": [(20.30, 85.82), (20.46, 85.88), (22.26, 84.85)], "Bihar": [(25.59, 85.14), (24.80, 85.00), (26.12, 85.39)],
    "Kerala": [(9.93, 76.27), (8.52, 76.94), (11.26, 75.78)], "Haryana": [(28.46, 77.03), (28.41, 77.31), (29.15, 75.72)],
}
VARS = "temperature_2m_max,relative_humidity_2m_mean,wind_speed_10m_mean,shortwave_radiation_sum,cloud_cover_mean"
LATE_IDS = {"india_grid": "india_grid_late", "india_grid_b": "india_grid_b_late"}


def log(msg: str) -> None:
    print(msg, flush=True)


def point_weather(lat: float, lon: float) -> pd.DataFrame:
    cache = RAW / "wx" / f"{lat}_{lon}.json"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        last = "no response"
        for attempt in range(8):
            try:
                r = httpx.get("https://archive-api.open-meteo.com/v1/archive", timeout=120, params={
                    "latitude": lat, "longitude": lon, "start_date": START, "end_date": END, "timezone": "Asia/Kolkata", "daily": VARS})
                if r.status_code == 200:
                    cache.write_text(r.text, encoding="utf-8")
                    time.sleep(1.5)
                    break
                last = f"HTTP {r.status_code} {r.text[:100]}"
            except httpx.HTTPError as exc:
                last = f"{type(exc).__name__}: {exc}"
            time.sleep(8 * (attempt + 1))
        else:
            raise RuntimeError(f"Open-Meteo failed for {lat},{lon}: {last}")
    d = pd.DataFrame(json.loads(cache.read_text(encoding="utf-8"))["daily"]).set_index("time")
    d.index = pd.to_datetime(d.index)
    return d.astype(float)


def state_weather(state: str) -> pd.DataFrame:
    parts = [point_weather(lat, lon) for lat, lon in CITIES[state]]
    m = sum(parts) / len(parts)
    return pd.DataFrame({"tmax": m["temperature_2m_max"], "rh": m["relative_humidity_2m_mean"], "wind": m["wind_speed_10m_mean"] / 3.6,   # km/h -> m/s
                         "solar": m["shortwave_radiation_sum"] / 3.6, "cloud": m["cloud_cover_mean"] / 100.0})                          # MJ/m2 -> kWh/m2; % -> 0..1


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    csv = RAW / "POSOCO_data.csv"
    if not csv.exists():
        log("1. downloading the daily Grid-India compilation ...")
        r = httpx.get(DEMAND_URL, timeout=180, follow_redirects=True)
        r.raise_for_status()
        csv.write_bytes(r.content)
    a = pd.read_csv(csv)
    a["date"] = pd.to_datetime(a["yyyymmdd"].astype(str), format="%Y%m%d")
    a = a.set_index("date").copy()
    log(f"   compilation: {a.index.min().date()} to {a.index.max().date()}")
    ledger = open_ledger()
    manifest = ROOT / "data" / "MANIFEST.json"
    for src, late in LATE_IDS.items():
        rows, dropped = [], {}
        for st in GROUPS[src]:
            d = a[f"{DEMAND_COL.get(st, st)}: EnergyMet"].dropna()
            d = d[(d.index >= START) & (d.index <= END) & (d > 0)]
            p = pd.DataFrame({"city": st, "date": d.index, "demand_mu": d.to_numpy()}).join(state_weather(st), on="date").dropna(subset=STRESS)
            if len(p) < MIN_DAYS:
                dropped[st] = int(len(p))
                continue
            fit = expected_log(p["date"].reset_index(drop=True), np.log(p["demand_mu"].to_numpy()))
            p["outcome"] = 100.0 * (np.log(p["demand_mu"].to_numpy()) - fit)
            p["expected_mu"] = np.exp(fit)
            rows.append(p)
        panel = pd.concat(rows, ignore_index=True)[["city", "date", *STRESS, "outcome", "demand_mu", "expected_mu"]].sort_values(["city", "date"]).reset_index(drop=True)
        out = PROC / f"{late}_panel.parquet"
        panel.to_parquet(out, index=False)
        qc = {
            "title": f"India daily electricity supplied x weather, the 8 states of {src}, AFTER the discovery window ({START} to {END})",
            "provenance": "REAL", "role": f"later-data replication of {src}", "rows": int(len(panel)), "states": sorted(panel["city"].unique().tolist()),
            "date_start": str(panel["date"].min().date()), "date_end": str(panel["date"].max().date()), "states_dropped_for_too_few_days": dropped,
            "sources": {"demand": "Robbie Andrew's daily compilation of Grid-India (POSOCO) reports, EnergyMet per state, https://robbieandrew.github.io/india/",
                        "weather": "Open-Meteo historical archive (ERA5), CC BY 4.0, daily values averaged over 3 large cities per state (Delhi: 1)"},
            "rule": "A pair found in the discovery panel counts as replicated on later data when the engine, with its unchanged pre-set rules, keeps the same pair in this panel after conditional selection.",
            "limitations": [
                "Same grid operator and the same reporting system as the discovery data: what is new is the period, not the source.",
                "Weather is averaged over 3 cities per state, not the state-wide ERA5 average used for discovery.",
                "The outcome is electricity supplied (grid stress), not health."],
        }
        qc_path = PROC / f"{late}_panel_qc.json"
        qc_path.write_text(json.dumps(qc, indent=2), encoding="utf-8")
        for pth in (out, qc_path):
            register_file(ledger, pth, "dataset", {"provenance": "REAL", "description": f"India electricity, later data for {src} (Track D replication)"}, manifest_path=manifest)
        log(f"2. {late}: {len(panel)} state-days in {panel['city'].nunique()} states ({panel['date'].min().date()} to {panel['date'].max().date()}) -> {out.name}; registered in the ledger")
    return 0


if __name__ == "__main__":
    sys.exit(main())
