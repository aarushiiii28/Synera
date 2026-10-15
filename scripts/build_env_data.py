"""Build Environmental Stressor Panel."""

import pandas as pd
import numpy as np

from synera_core.data.openmeteo import fetch_openmeteo_archive, fetch_openmeteo_air_quality
from synera_core.config import find_repo_root
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger
from synera_core.data.cities import CITIES, START_DATE, END_DATE, calculate_heat_index

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
    ledger = open_ledger()

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
    
    h, _ = register_file(
        ledger=ledger,
        path=out_path,
        kind="dataset",
        meta={"description": "Environmental stressor panel (Open-Meteo weather + air quality)", "provenance": "REAL",
              "cities": list(CITIES), "start": START_DATE, "end": END_DATE},
    )
    print(f"Registered to ledger. Hash: {h}")

if __name__ == "__main__":
    main()

