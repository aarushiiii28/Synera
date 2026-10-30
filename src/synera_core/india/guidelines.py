"""Official thresholds the live recommendations rest on. Pure functions, no network, each one cites where its numbers come from.

* AQI: India's National Air Quality Index, CPCB 2014 (PM2.5 and PM10 sub-indices, six categories, health statements).
* Heat: IMD heat-wave criteria (Tmax and departure from normal, by terrain) and the NWS heat-index categories.
* Rain: IMD 24-hour rainfall categories.
* UV: WHO / WMO UV-index exposure categories.
* WHO 2021 air-quality guideline levels and the Indian NAAQS 24-hour standards, for context.
"""
from __future__ import annotations

# CPCB NAQI: (concentration low, concentration high, index low, index high); concentrations are 24-hour averages in ug/m3.
# The top band is open-ended in the CPCB table; it is capped at 500 using the customary upper ends 380 (PM2.5) and 510 (PM10).
_BREAKS = {
    "pm25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200), (90, 120, 201, 300), (120, 250, 301, 400), (250, 380, 401, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200), (250, 350, 201, 300), (350, 430, 301, 400), (430, 510, 401, 500)],
}
AQI_CATEGORIES = [(50, "Good", 0), (100, "Satisfactory", 1), (200, "Moderate", 2), (300, "Poor", 3), (400, "Very Poor", 4), (500, "Severe", 5)]
AQI_HEALTH = {
    "Good": "Minimal impact.",
    "Satisfactory": "May cause minor breathing discomfort to sensitive people.",
    "Moderate": "May cause breathing discomfort to people with lung disease such as asthma, and discomfort to people with heart disease, children and older adults.",
    "Poor": "May cause breathing discomfort to most people on prolonged exposure, and discomfort to people with heart disease.",
    "Very Poor": "May cause respiratory illness to people on prolonged exposure; effect is more pronounced in people with lung and heart disease.",
    "Severe": "May cause respiratory effects even on healthy people and serious health impacts on people with lung and heart disease; health impacts show even during light physical activity.",
}
WHO_PM25_24H, WHO_PM10_24H = 15.0, 45.0         # WHO 2021 air quality guidelines
NAAQS_PM25_24H, NAAQS_PM10_24H = 60.0, 100.0    # India NAAQS 2009


def sub_index(pollutant: str, conc: float | None) -> float | None:
    """CPCB sub-index (0-500) of one pollutant's 24-hour average; None when the concentration is missing or impossible."""
    if conc is None or conc != conc or conc < 0:
        return None
    for lo, hi, ilo, ihi in _BREAKS[pollutant]:
        if conc <= hi:
            return round(ilo + (ihi - ilo) * (conc - lo) / (hi - lo), 1)
    return 500.0


def aqi_category(index: float | None) -> tuple[str, int] | None:
    if index is None:
        return None
    for top, name, level in AQI_CATEGORIES:
        if index <= top:
            return name, level
    return "Severe", 5


def national_aqi(pm25_24h: float | None, pm10_24h: float | None) -> dict:
    """The AQI is the worst sub-index; CPCB requires at least one of PM2.5 or PM10 (and three pollutants for an official figure,
    so a PM-only value is reported as a PM-based index and says so)."""
    subs = {"pm25": sub_index("pm25", pm25_24h), "pm10": sub_index("pm10", pm10_24h)}
    have = {k: v for k, v in subs.items() if v is not None}
    if not have:
        return {"index": None, "category": None, "level": None, "driver": None, "sub_indices": subs}
    driver = max(have, key=have.get)
    cat = aqi_category(have[driver])
    return {"index": have[driver], "category": cat[0], "level": cat[1], "driver": driver, "sub_indices": subs}


# ---- heat ---------------------------------------------------------------------------------------------------------------
# IMD heat wave: Tmax at least this (plains 40, coastal 37, hills 30) AND departure from normal at least 4.5 C, or an absolute 45 C (plains).
_IMD_TMAX = {"plains": 40.0, "coastal": 37.0, "hills": 30.0}


def imd_heat(tmax_c: float | None, departure_c: float | None, terrain: str = "plains") -> dict:
    if tmax_c is None:
        return {"status": None, "basis": "Tmax missing"}
    floor = _IMD_TMAX.get(terrain, 40.0)
    basis = f"IMD criteria for {terrain}: Tmax at least {floor:g} C with departure from normal at least 4.5 C (severe: 6.5 C), or an absolute 45 C (severe 47 C) in the plains"
    if terrain == "plains" and tmax_c >= 47:
        return {"status": "SEVERE_HEAT_WAVE", "basis": basis}
    if terrain == "plains" and tmax_c >= 45:
        return {"status": "HEAT_WAVE", "basis": basis}
    if departure_c is None:
        return {"status": "HOT" if tmax_c >= floor else "NORMAL", "basis": basis + "; departure from normal unavailable, so the departure criterion was not applied"}
    if tmax_c >= floor and departure_c >= 6.5:
        return {"status": "SEVERE_HEAT_WAVE", "basis": basis}
    if tmax_c >= floor and departure_c >= 4.5:
        return {"status": "HEAT_WAVE", "basis": basis}
    return {"status": "HOT" if tmax_c >= floor else "NORMAL", "basis": basis}


def heat_index_category(hi_c: float | None) -> tuple[str, int] | None:
    """NWS heat-index categories converted to Celsius (80, 90, 103, 125 F = 26.7, 32.2, 39.4, 51.7 C); below 80 F the NWS names no category."""
    if hi_c is None:
        return None
    for top, name, level in [(26.7, "Not elevated", 0), (32.2, "Caution", 1), (39.4, "Extreme caution", 2), (51.7, "Danger", 3)]:
        if hi_c < top:
            return name, level
    return "Extreme danger", 4


# ---- rain, UV -----------------------------------------------------------------------------------------------------------
def imd_rain(mm_24h: float | None) -> tuple[str, int] | None:
    """IMD 24-hour rainfall categories."""
    if mm_24h is None:
        return None
    for top, name, level in [(2.4, "No or trace rain", 0), (15.5, "Light to moderate", 1), (64.5, "Rather heavy", 2), (115.6, "Heavy", 3), (204.5, "Very heavy", 4)]:
        if mm_24h < top:
            return name, level
    return "Extremely heavy", 5


def uv_category(uv: float | None) -> tuple[str, int] | None:
    if uv is None:
        return None
    for top, name, level in [(3, "Low", 0), (6, "Moderate", 1), (8, "High", 2), (11, "Very high", 3)]:
        if uv < top:
            return name, level
    return "Extreme", 4


def composite_risk(aqi_level: int | None, heat_level: int | None, rain_level: int | None) -> dict:
    """Map layer 'composite environmental risk': the worst of the individual hazards on a common 0-1 scale, and which one drives it.
    Deliberately simple and transparent (no weights to defend); the SYNERA engine's interaction analysis is on the city panel."""
    parts = {"air quality": (aqi_level, 5), "heat": (heat_level, 4), "rain": (rain_level, 5)}
    scores = {k: lvl / top for k, (lvl, top) in parts.items() if lvl is not None}
    if not scores:
        return {"score": None, "driver": None, "tier": None}
    driver = max(scores, key=scores.get)
    s = scores[driver]
    tier = "LOW" if s <= 0.3 else "MODERATE" if s <= 0.5 else "HIGH" if s <= 0.7 else "SEVERE"
    return {"score": round(s, 3), "driver": driver, "tier": tier}
