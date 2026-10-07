import os
import json
import time
import httpx
from typing import Dict, Any

CACHE_FILE = os.path.join(os.path.dirname(__file__), "../../../artifacts/openmeteo_cache.json")

def get_forecast(region: str) -> Dict[str, Any]:
    # Very simple mock coordinate mapping for demonstration
    coords = {"Seattle": {"lat": 47.6062, "lon": -122.3321}, "New York": {"lat": 40.7128, "lon": -74.0060}}
    lat = coords.get(region, coords["Seattle"])["lat"]
    lon = coords.get(region, coords["Seattle"])["lon"]
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m"
    
    # Try cache first
    cache_data = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache_data = json.load(f)
            
    if region in cache_data and time.time() - cache_data[region].get("ts", 0) < 3600:
        return cache_data[region]["data"]
        
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        
        cache_data[region] = {"ts": time.time(), "data": data}
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
        return data
    except Exception as e:
        if region in cache_data:
            return cache_data[region]["data"]
        raise Exception(f"Failed to fetch forecast and no cache available: {e}")

def evaluate_risk(region: str, findings: list) -> Dict[str, Any]:
    """
    Evaluates risk based on forecast and findings.
    """
    try:
        forecast = get_forecast(region)
    except Exception as e:
        forecast = {}
        
    # Evaluate fitted response surface of findings (mock evaluation)
    uplift = 0.15
    tier = "HIGH"
    
    return {
        "region": region,
        "risk_tier": tier,
        "interaction_uplift": uplift,
        "uncertainty_lower": 0.10,
        "uncertainty_upper": 0.20,
        "source_findings": [f.id for f in findings],
        "simulated_only": all(f.provenance == "SIMULATED" for f in findings) if findings else True
    }
