import pandas as pd
import numpy as np
from pathlib import Path
from synera_core.provenance.manifest import register_file
from synera_core.provenance.ledger import Ledger
from synera_core.config import find_repo_root
import json
import hashlib

def generate_benchmark(snr: float = 2.0, rho: float = 0.5, n_per_city: int = 100, 
                       n_decoys: int = 5, seed: int = 42, 
                       out_dir: Path = None, ledger: Ledger = None):
    """Generate semi-synthetic benchmark with planted ground truth."""
    if out_dir is None:
        out_dir = find_repo_root() / "data" / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    rng = np.random.default_rng(seed)
    
    # 1. Load Real Covariates
    env_df = pd.read_parquet(find_repo_root() / "data" / "processed" / "env_panel.parquet")
    
    # Use contiguous windows per city to preserve true AR(1)
    def get_window(g):
        g = g.sort_values("date")
        if n_per_city is None or n_per_city >= len(g) or n_per_city <= 0:
            return g
        start_idx = rng.integers(0, len(g) - n_per_city + 1)
        return g.iloc[start_idx : start_idx + n_per_city]
        
    env_df = pd.concat([get_window(g) for _, g in env_df.groupby("city")])
    env_df = env_df.reset_index(drop=True)
    
    features = ["heat_index", "pm25", "rh", "o3", "drought_index", "pm10", "no2", "uv", "wind", "precip"]
    
    # Standardize per city
    for f in features:
        env_df[f] = env_df.groupby("city")[f].transform(lambda x: (x - x.mean()) / (x.std() + 1e-9))
    
    env_df = env_df.dropna(subset=features)
    
    # 2. Planted Truth Table
    truth = {
        "interactions": [
            {"var1": "heat_index", "var2": "pm25", "type": "SYNERGISTIC", "effect": 1.5},
            {"var1": "heat_index", "var2": "rh", "type": "ANTAGONISTIC", "effect": -1.5},
            {"var1": "o3", "var2": "heat_index", "type": "NONLINEAR", "effect": 2.0}
        ],
        "decoys": []
    }
    
    # 3. Generate Outcome
    y = np.zeros(len(env_df))
    
    # Baseline + city effect + seasonal
    city_effects = {city: rng.normal(0, 1) for city in env_df['city'].unique()}
    y += env_df['city'].map(city_effects)
    
    day_of_year = pd.to_datetime(env_df['date']).dt.dayofyear
    env_df['sin_doy'] = np.sin(2 * np.pi * day_of_year / 365)
    env_df['cos_doy'] = np.cos(2 * np.pi * day_of_year / 365)
    y += env_df['sin_doy'].values + env_df['cos_doy'].values
    
    # Main effects for the interacting vars
    for var in ["heat_index", "pm25", "rh", "o3"]:
        y += 0.5 * env_df[var].values
        
    # Planted interactions
    # SYNERGISTIC: heat_index x pm25
    y += 1.5 * (env_df["heat_index"] * env_df["pm25"]).values
    
    # ANTAGONISTIC: heat_index x rh
    y += -1.5 * (env_df["heat_index"] * env_df["rh"]).values
    
    # NONLINEAR: o3 x heat_index (sigmoid switch on heat_index)
    sigmoid_hi = 1 / (1 + np.exp(-3 * env_df["heat_index"].values))
    y += 2.0 * env_df["o3"].values * sigmoid_hi
    
    # Decoys (main effects only)
    decoy_candidates = ["drought_index", "pm10", "no2", "uv", "wind", "precip"]
    chosen_decoys = rng.choice(decoy_candidates, min(n_decoys, len(decoy_candidates)), replace=False)
    for dc in chosen_decoys:
        eff = rng.choice([1.0, -1.0])
        y += eff * env_df[dc].values
        truth["decoys"].append({"var": dc, "effect": eff})
        
    # AR(1) noise per city
    noise = np.zeros(len(env_df))
    for city in env_df['city'].unique():
        idx = env_df['city'] == city
        n_city = idx.sum()
        city_noise = np.zeros(n_city)
        city_noise[0] = rng.normal(0, 1)
        for t in range(1, n_city):
            city_noise[t] = rho * city_noise[t-1] + np.sqrt(1 - rho**2) * rng.normal(0, 1)
        noise[idx] = city_noise
        
    signal_var = np.var(y)
    target_noise_var = signal_var / snr
    noise = noise * np.sqrt(target_noise_var)
    
    env_df["outcome"] = y + noise
    env_df["provenance"] = "SIMULATED"
    
    # 4. Save and Register
    out_path = out_dir / f"benchmark_snr{snr}_seed{seed}.parquet"
    env_df.to_parquet(out_path, index=False)
    
    truth_path = out_dir / f"benchmark_truth_snr{snr}_seed{seed}.json"
    with open(truth_path, "w") as f:
        json.dump(truth, f, indent=2)
        
    if ledger:
        register_file(ledger, out_path, "dataset", {"snr": snr, "rho": rho, "seed": seed})
        register_file(ledger, truth_path, "dataset", {"type": "truth", "seed": seed})
        
    return out_path, truth_path
