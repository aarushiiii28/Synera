"""Orchestration for the India live map: provider -> normalise -> validate -> SYNERA engine -> explanation -> recommendations."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from synera_core.india import climatology as clim
from synera_core.india import engine, providers, recommend
from synera_core.india.cities import BY_ID, CITIES
from synera_core.india.normalize import build_reading, map_summary

LAYERS = [
    {"id": "aqi", "label": "Air quality", "field": "aqi", "unit": "AQI", "legend": [[0, 50, "Good"], [51, 100, "Satisfactory"], [101, 200, "Moderate"], [201, 300, "Poor"], [301, 400, "Very Poor"], [401, 500, "Severe"]],
     "note": "CPCB National AQI computed from modelled PM2.5 / PM10 (24-hour mean). PM-based only; modelled, not a monitor reading."},
    {"id": "temperature", "label": "Temperature", "field": "temperature_c", "unit": "°C", "legend": [[-5, 10, "Cold"], [10, 22, "Cool"], [22, 30, "Warm"], [30, 38, "Hot"], [38, 45, "Very hot"], [45, 55, "Extreme"]], "note": "2 m air temperature, model analysis."},
    {"id": "humidity", "label": "Humidity", "field": "humidity_pct", "unit": "%", "legend": [[0, 30, "Dry"], [30, 50, "Comfortable"], [50, 70, "Humid"], [70, 85, "Very humid"], [85, 100, "Saturated"]], "note": "Relative humidity at 2 m, model analysis."},
    {"id": "rainfall", "label": "Rainfall", "field": "rain_24h_mm", "unit": "mm / 24 h", "legend": [[0, 2.4, "None"], [2.4, 15.5, "Light"], [15.5, 64.5, "Rather heavy"], [64.5, 115.6, "Heavy"], [115.6, 400, "Very heavy"]], "note": "Rain over the last 24 hours, IMD categories."},
    {"id": "wind", "label": "Wind", "field": "wind_kmh", "unit": "km/h", "legend": [[0, 8, "Stagnant"], [8, 20, "Light"], [20, 40, "Moderate"], [40, 60, "Strong"], [60, 200, "Very strong"]], "note": "10 m wind speed, model analysis. Low wind limits pollution dispersal."},
    {"id": "risk", "label": "Composite risk", "field": "risk", "unit": "0-1", "legend": [[0, 0.3, "Low"], [0.3, 0.5, "Moderate"], [0.5, 0.7, "High"], [0.7, 1.0, "Severe"]],
     "note": "The worst of air quality, heat (NWS heat-index category) and rain (IMD category), each scaled 0-1. The driver is named on every city."},
]
SOURCE_DOCS = {"Open-Meteo": "https://open-meteo.com/en/docs", "CAMS": "https://open-meteo.com/en/docs/air-quality-api", "OpenAQ": "https://docs.openaq.org", "CPCB": "https://data.gov.in",
               "FIRMS": "https://firms.modaps.eosdis.nasa.gov/api"}


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def _src(name: str, role: str, kind: str, meta: dict, doc: str | None = None) -> dict:
    return {"name": name, "role": role, "kind": kind, "status": meta.get("status"), "fetched_at": _iso(meta.get("fetched_at")), "note": meta.get("note"), "docs": doc}


def overview() -> dict[str, Any]:
    """Every supported city in two batched calls (weather, air quality): the data behind the map markers and layers."""
    try:
        wl, wm = providers.weather(CITIES)
    except providers.SourceError as exc:
        return {"available": False, "reason": f"The weather provider could not be reached ({exc}) and nothing is cached.", "cities": [], "layers": LAYERS}
    try:
        al, am = providers.air(CITIES)
    except providers.SourceError as exc:
        al, am = [None] * len(CITIES), {"status": "ERROR", "note": str(exc)}
    cities = [map_summary(build_reading(c, w, a)) for c, w, a in zip(CITIES, wl, al)]
    return {"available": True, "generated_at": _iso(time.time()), "layers": LAYERS, "cities": cities, "national": national_summary(cities),
            "sources": [_src("Open-Meteo forecast API", "weather", "MODEL_ANALYSIS and FORECAST", wm, SOURCE_DOCS["Open-Meteo"]),
                        _src("Open-Meteo air-quality API (CAMS)", "air quality", "MODEL_ANALYSIS and FORECAST", am, SOURCE_DOCS["CAMS"])]}


def national_summary(cities: list[dict]) -> dict:
    ok = [c for c in cities if c["aqi"] is not None]
    cats: dict[str, int] = {}
    for c in ok:
        cats[c["aqi_category"]] = cats.get(c["aqi_category"], 0) + 1
    alerts = []
    for c in cities:
        if c["aqi_level"] is not None and c["aqi_level"] >= 4:
            alerts.append({"city": c["name"], "id": c["id"], "kind": "AIR", "level": "CRITICAL" if c["aqi_level"] == 5 else "HIGH_PRIORITY", "text": f"AQI {c['aqi']:.0f}, {c['aqi_category']}"})
        if c["imd_heat"] in ("HEAT_WAVE", "SEVERE_HEAT_WAVE"):
            alerts.append({"city": c["name"], "id": c["id"], "kind": "HEAT", "level": "CRITICAL" if c["imd_heat"] == "SEVERE_HEAT_WAVE" else "HIGH_PRIORITY", "text": "forecast maximum meets IMD heat-wave criteria"})
        if (c["rain_24h_mm"] or 0) >= 64.5 or (c["rain_next_mm"] or 0) >= 64.5:
            alerts.append({"city": c["name"], "id": c["id"], "kind": "RAIN", "level": "HIGH_PRIORITY", "text": "heavy rain (64.5 mm or more in a day)"})
    top = lambda key, n=5: [{"id": c["id"], "name": c["name"], "value": c[key], "category": c.get("aqi_category") if key == "aqi" else None} for c in sorted((c for c in cities if c[key] is not None), key=lambda c: -c[key])[:n]]  # noqa: E731
    return {"cities_with_air_data": len(ok), "aqi_categories": cats, "hotspots_air": top("aqi"), "hottest": top("temperature_c", 3), "alerts": sorted(alerts, key=lambda a: a["level"] != "CRITICAL")[:12],
            "median_aqi": float(pd.Series([c["aqi"] for c in ok]).median()) if ok else None}


def _today_values(reading: dict, w: dict) -> dict[str, float | None]:
    today = next((d for d in reading["daily"] if d["is_today"]), None)
    now = pd.Timestamp(w["current"]["time"])
    hrs = pd.DataFrame({"t": pd.to_datetime(w["hourly"]["time"]), "rh": w["hourly"]["relative_humidity_2m"]}).dropna()
    rh = hrs[hrs["t"].dt.normalize() == now.normalize()]["rh"]
    return {"tmax": today["tmax_c"] if today else None, "rh": float(rh.mean()) if len(rh) >= 6 else None}


def city_detail(city_id: str, findings: list[dict]) -> dict[str, Any]:
    city = BY_ID[city_id]
    try:
        wl, wm = providers.weather([city])
    except providers.SourceError as exc:
        return {"available": False, "city": city, "reason": f"The weather provider could not be reached ({exc}) and nothing is cached for this city. No values are shown rather than guessed ones."}
    w = wl[0]
    try:
        al, am = providers.air([city])
        a = al[0]
    except providers.SourceError as exc:
        a, am = None, {"status": "ERROR", "note": str(exc)}
    today = pd.Timestamp(w["current"]["time"]).normalize()
    history = providers.daily_history(city)
    norm = clim.normals(history, today) if history else {}
    cp, cpm = providers.cpcb_latest(city)
    oq, oqm = providers.openaq_latest(city)
    fi, fim = providers.firms_fires(city)
    station = None
    if cp:
        station = {**cp, "source": "CPCB", "source_label": "CPCB station average (data.gov.in)", "time": cp.get("last_update")}
    elif oq:
        station = {**oq, "source": "OpenAQ", "source_label": "OpenAQ stations (median)", "time": oq.get("latest_utc")}
    tmax_norm = norm.get("_tmax")
    probe = build_reading(city, w, a)
    tm = next((d["tmax_c"] for d in probe["daily"] if d["is_today"]), None)
    dep = (tm - tmax_norm["mean"]) if (tm is not None and tmax_norm) else None
    stale = "stale" in (wm.get("status"), am.get("status"))
    sources = [_src("Open-Meteo forecast API", "weather and forecast", "MODEL_ANALYSIS and FORECAST", wm, SOURCE_DOCS["Open-Meteo"]),
               _src("Open-Meteo air-quality API (CAMS)", "air quality and forecast", "MODEL_ANALYSIS and FORECAST", am, SOURCE_DOCS["CAMS"]),
               _src("Open-Meteo archive (2023-2025)", "this city's normal for the season", "HISTORY", {"status": "cached" if history else "ERROR", "note": None if history else "unavailable: engine comparison with normal is skipped"}),
               _src("CPCB via data.gov.in", "station air-quality averages", "OBSERVATION", cpm, SOURCE_DOCS["CPCB"]), _src("OpenAQ", "station air-quality readings", "OBSERVATION", oqm, SOURCE_DOCS["OpenAQ"]),
               _src("NASA FIRMS", "satellite fire detections", "SATELLITE DETECTION", fim, SOURCE_DOCS["FIRMS"]),
               {"name": "IMD", "role": "official heat-wave and rainfall criteria", "kind": "THRESHOLDS", "status": "USED_AS_THRESHOLDS", "fetched_at": None, "note": "IMD publishes no open, keyless observation API; its published criteria are applied to the model values.", "docs": "https://mausam.imd.gov.in"}]
    reading = build_reading(city, w, a, station=station, fires=fi, departure_c=dep, sources=sources)
    scen = engine.scenario_for_city(city, w, a, history, today)
    grid = engine.grid_stress(city["state"], _today_values(reading, w), findings)
    recs = recommend.build(reading, scen, grid, stale=stale)
    return {"available": True, "generated_at": _iso(time.time()), **reading, "engine": {"scenario": scen, "grid": grid}, "recommendations": recs, "explain": explain(reading, scen, grid, recs)}


def explain(r: dict, scen: dict, grid: dict, recs: list[dict]) -> dict:
    d, m = r["derived"], r["metrics"]
    drivers = []
    aqi = d["aqi"]
    if aqi["index"] is not None:
        drivers.append({"parameter": "Air quality", "value": f"AQI {aqi['index']:.0f} ({aqi['category']}), driven by {'PM2.5' if aqi['driver'] == 'pm25' else 'PM10'}", "level": aqi["level"], "max": 5, "basis": "CPCB National AQI breakpoints"})
    if d["heat_index"]:
        drivers.append({"parameter": "Heat", "value": f"heat stress {d['heat_stress_c']:.0f} °C ({d['heat_index']['category']})", "level": d["heat_index"]["level"], "max": 4, "basis": "NWS heat-index categories; IMD heat-wave criteria"})
    rain = max([x for x in (d["rain"], d["rain_next"]) if x], key=lambda x: x["level"], default=None)
    if rain:
        drivers.append({"parameter": "Rain", "value": rain["category"], "level": rain["level"], "max": 5, "basis": "IMD 24-hour rainfall categories"})
    low_wind = m["wind_kmh"]["value"] is not None and m["wind_kmh"]["value"] < 8
    flags = []
    pairs = [("heat and PM2.5 both elevated", (d["heat_index"] or {}).get("level", 0) >= 2 and (aqi["level"] or 0) >= 2, ("heat_index", "pm25")),
             ("high humidity with poor air quality", (m["humidity_pct"]["value"] or 0) >= 70 and (aqi["level"] or 0) >= 3, ("rh", "pm25")),
             ("low wind with poor air quality", low_wind and (aqi["level"] or 0) >= 2, ("wind", "pm25")),
             ("extreme heat with low wind", low_wind and (d["heat_index"] or {}).get("level", 0) >= 2, ("heat_index", "wind"))]
    terms = (scen or {}).get("interaction_terms", []) if scen and scen.get("available") else []
    for text, present, (x, y) in pairs:
        if not present:
            continue
        t = next((t for t in terms if {t["a"], t["b"]} == {x, y}), None)
        flags.append({"condition": text, "engine_term": t, "verdict": ("SUPPORTED by the engine's learned interaction (range excludes zero)" if t and t["supported"] else
                      "co-occurring, but the engine finds no supported interaction for this pair (range includes zero)" if t else "co-occurring; the engine has no estimate for this pair here")})
    skill = (scen or {}).get("model_skill")
    return {
        "drivers": drivers, "composite": d["composite"], "conditions": flags,
        "engine": {
            "scenario_model": ({"available": True, "decomposition": scen["contributions"], "method": "Exact decomposition of the model's terms (a product term is split equally between its two stressors, the Shapley split for two players). This is not a LightGBM-SHAP run.",
                                "skill": skill, "plain": f"The model explains a very small share of week-to-week variation in deaths (R² {skill['r2_leave_states_out']:.3f} on states it never saw) and its calibration slope is {skill['calibration_slope']:.2f}; "
                                f"{skill['interaction_pairs_excluding_zero']} of {skill['interaction_pairs_tested']} pairwise interactions stood out, against about {skill['expected_by_chance']:.1f} expected by chance, so individual interactions are not established."}
                               if scen and scen.get("available") else {"available": False, "reason": (scen or {}).get("reason")}),
            "grid_findings": grid},
        "basis_count": {"THRESHOLD": sum(x["basis"] == "THRESHOLD" for x in recs), "ENGINE": sum(x["basis"] == "ENGINE" for x in recs)},
        "not_done": ["The discovery stage's LightGBM and SHAP analysis is not run on live readings.", "Causes are not inferred: everything above is association or an official threshold.",
                     "Nothing here is medical advice or a prediction for any individual."]}
