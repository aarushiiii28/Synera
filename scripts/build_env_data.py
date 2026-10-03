"""Build Environmental Stressor Panel."""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

from synera_core.data.nasa_power import fetch_power_point
from synera_core.data.openmeteo import fetch_openmeteo_archive, fetch_openmeteo_air_quality
from synera_core.config import find_repo_root
from synera_core.provenance.manifest import register_file
from synera_core.provenance.ledger import Ledger

CITIES = {
    "Ludhiana": {"lat": 30.9010, "lon": 75.8523},
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Beijing": {"lat": 39.9042, "lon": 116.4074},
    "Cairo": {"lat": 30.0444, "lon": 31.2357},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
    "Phoenix": {"lat": 33.4484, "lon": -112.0740},
    "Jakarta": {"lat": -6.2088, "lon": 106.8456}
}

START_DATE = "2022-08-01"
END_DATE = "2023-12-31"

def calculate_heat_index(t_c: pd.Series, rh: pd.Series) -> pd.Series:
    """
    Calculate Heat Index using Rothfusz regression.
    Formula is valid for T >= 80F and RH >= 40%.
    We convert T from Celsius to Fahrenheit, calculate, and convert back.
    For conditions outside the valid range, it defaults to the original temperature.
    """
    t_f = t_c * 9/5 + 32
    
    # Simple unadjusted HI
    hi = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    
    # Rothfusz regression
    rothfusz = (
        -42.379 + 2.04901523 * t_f + 10.14333127 * rh 
        - 0.22475541 * t_f * rh - 6.83783e-3 * t_f**2 
        - 5.481717e-2 * rh**2 + 1.22874e-3 * t_f**2 * rh 
        + 8.5282e-4 * t_f * rh**2 - 1.99e-6 * t_f**2 * rh**2
    )
    
    # Apply conditions
    valid_mask = (t_f >= 80) & (rh >= 40)
    hi = np.where(valid_mask, rothfusz, hi)
    
    # Convert back to Celsius
    return pd.Series((hi - 32) * 5/9, index=t_c.index)

def fetch_city_data(city: str, coords: dict) -> pd.DataFrame:
    print(f"Fetching data for {city}...")
    lat = coords["lat"]
    lon = coords["lon"]
    
    # 1. Fetch Open-Meteo Weather
    weather = fetch_openmeteo_archive(
        latitude=lat,
        longitude=lon,
        start_date=START_DATE,
        end_date=END_DATE,
        variables=["temperature_2m_max", "temperature_2m_mean", "relative_humidity_2m_mean", "precipitation_sum", "wind_speed_10m_max"],
        is_daily=True
    )
    
    w_df = pd.DataFrame(weather["daily"])
    w_df["date"] = pd.to_datetime(w_df["time"])
    w_df = w_df.drop(columns=["time"])
    
    # 2. Fetch Open-Meteo Air Quality
    # Note: air quality is hourly, we need to aggregate to daily
    aq = fetch_openmeteo_air_quality(
        latitude=lat,
        longitude=lon,
        start_date=START_DATE,
        end_date=END_DATE,
        variables=["pm10", "pm2_5", "ozone", "nitrogen_dioxide", "uv_index"]
    )
    
    aq_df = pd.DataFrame(aq["hourly"])
    aq_df["date"] = pd.to_datetime(aq_df["time"]).dt.date
    aq_df = aq_df.drop(columns=["time"])
    
    # Aggregate hourly AQ to daily means
    aq_daily = aq_df.groupby("date").mean().reset_index()
    aq_daily["date"] = pd.to_datetime(aq_daily["date"])
    
    # 3. Merge
    df = pd.merge(w_df, aq_daily, on="date", how="left")
    df["city"] = city
    
    # Rename for consistency
    df = df.rename(columns={
        "temperature_2m_max": "tmax",
        "temperature_2m_mean": "tmean",
        "relative_humidity_2m_mean": "rh",
        "precipitation_sum": "precip",
        "wind_speed_10m_max": "wind",
        "pm2_5": "pm25",
        "ozone": "o3",
        "nitrogen_dioxide": "no2",
        "uv_index": "uv"
    })
    
    return df

def main():
    repo_root = find_repo_root()
    db_path = repo_root / "artifacts" / "synera.db"
    key_path = repo_root / "configs" / "signer.key"
    
    ledger = None
    if db_path.exists() and key_path.exists():
        ledger = Ledger(db_path, key_path)
    
    all_dfs = []
    for city, coords in CITIES.items():
        try:
            df = fetch_city_data(city, coords)
            all_dfs.append(df)
        except Exception as e:
            print(f"Error fetching {city}: {e}")
            
    if not all_dfs:
        print("No data fetched.")
        return
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    # Calculate Heat Index
    final_df["heat_index"] = calculate_heat_index(final_df["tmean"], final_df["rh"])
    
    # Calculate Drought Index (30-day rolling precipitation z-score against city climatology, sign-flipped)
    final_df = final_df.sort_values(["city", "date"])
    final_df["precip_30d"] = final_df.groupby("city")["precip"].transform(lambda x: x.rolling(30, min_periods=1).sum())
    
    def calc_zscore(x):
        std = x.std()
        if std == 0 or pd.isna(std):
            return pd.Series(0, index=x.index)
        return (x - x.mean()) / std
        
    final_df["precip_z"] = final_df.groupby("city")["precip_30d"].transform(calc_zscore)
    final_df["drought_index"] = -final_df["precip_z"]
    
    # Provenance
    final_df["provenance"] = "REAL"
    
    # Reorder columns
    cols = ["city", "date", "tmax", "tmean", "rh", "heat_index", "precip", "drought_index", 
            "pm25", "pm10", "o3", "no2", "uv", "wind", "provenance"]
    
    # Some columns might be missing if API failed to return them
    for c in cols:
        if c not in final_df.columns:
            final_df[c] = np.nan
            
    final_df = final_df[cols]
    
    # Physical range checks (flagging rows)
    final_df["flag_temp"] = ~final_df["tmax"].between(-60, 60, inclusive="both")
    final_df["flag_rh"] = ~final_df["rh"].between(0, 100, inclusive="both")
    final_df["flag_pm"] = (final_df["pm25"] < 0) | (final_df["pm10"] < 0)
    
    out_dir = repo_root / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "env_panel.parquet"
    
    final_df.to_parquet(out_path, index=False)
    print(f"\nSaved env panel to {out_path} ({len(final_df)} rows).")
    
    if ledger:
        h, _ = register_file(
            ledger=ledger,
            path=out_path,
            kind="dataset",
            meta={"description": "Environmental stressor panel", "provenance": "REAL"}
        )
        print(f"Registered to ledger. Hash: {h}")

if __name__ == "__main__":
    main()
