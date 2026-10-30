"""Ranked, evidence-backed recommendations for one city. Rule-based and auditable: every recommendation says what is happening, why, who is affected,
what to do, how urgent it is, for how long, how far to trust it, and which numbers and thresholds support it. A recommendation rests on either an
official ``THRESHOLD`` (CPCB / IMD / WHO) or on the SYNERA ``ENGINE`` output, never on both without saying so.

These are public-health and operations advisories, not medical advice and not a prediction for any individual.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from synera_core.india import guidelines as g

URGENCY = ["INFORMATIONAL", "ADVISORY", "HIGH_PRIORITY", "CRITICAL"]
WINDOWS = ["IMMEDIATE", "NEXT_HOURS", "FORECAST_PERIOD"]
GROUPS = {"citizens": "Citizens", "sensitive": "People with asthma, heart or lung disease, older adults, pregnant women", "children": "Children", "schools": "Schools",
          "commuters": "Commuters", "outdoor_workers": "Outdoor workers", "hospitals": "Hospitals and clinics", "authorities": "Authorities", "utilities": "Power utilities"}


def _ev(label: str, value: Any, threshold: str | None, source: str) -> dict:
    return {"label": label, "value": value, "threshold": threshold, "source": source}


def _confidence(r: dict, needs: list[str], kinds_ok: bool = True, engine: bool = False, stale: bool = False) -> dict:
    have = [r["metrics"].get(n, {}).get("value") is not None for n in needs if n in r["metrics"]]
    frac = (sum(have) / len(have)) if have else 1.0
    obs = any(r["metrics"].get(n, {}).get("kind") == "OBSERVATION" for n in needs)
    score = 0.95 * frac * (1.0 if obs else 0.8) * (0.9 if stale else 1.0)
    why = ["complete inputs" if frac == 1 else f"{int((1 - frac) * 100)}% of needed inputs missing",
           "station observation" if obs else "model-analysis values, not a station reading"]
    if stale:
        why.append("a provider failed and the last good copy is shown")
    if engine:
        score = min(score, 0.45)
        why.append("model learned in the US and transferred here")
    level = "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW"
    return {"level": level, "score": round(score, 2), "why": "; ".join(why)}


def _quiet_window(series: dict | None, col: str = "pm25", hours: int = 3) -> dict | None:
    """The cleanest and the dirtiest ``hours``-long windows in the next 24 hours of the model forecast (clock times, IST)."""
    if not series or col not in series:
        return None
    i = series["now_index"]
    seg = pd.Series(series[col][i + 1:i + 25], index=series["time"][i + 1:i + 25], dtype=float)
    if seg.notna().sum() < 18:
        return None
    roll = seg.rolling(hours, min_periods=hours).mean().dropna()
    if roll.empty:
        return None
    lo_end, hi_end = roll.idxmin(), roll.idxmax()
    pos = lambda end: list(seg.index).index(end)                                                  # noqa: E731
    span = lambda end: f"{seg.index[pos(end) - hours + 1][11:16]}-{pd.Timestamp(end).strftime('%H:%M')}"   # noqa: E731
    return {"cleanest": span(lo_end), "cleanest_value": float(roll.min()), "dirtiest": span(hi_end), "dirtiest_value": float(roll.max())}


def build(r: dict, scenario: dict | None, grid: dict | None, stale: bool = False) -> list[dict]:
    """``r``: the normalised reading; ``scenario`` / ``grid``: outputs of ``engine``."""
    d, m = r["derived"], r["metrics"]
    aqi, recs = d["aqi"], []
    wind = m["wind_kmh"]["value"]
    pm25_v, pm10_v = aqi.get("pm25_24h"), aqi.get("pm10_24h")
    win = _quiet_window(r.get("series"))

    def add(id_: str, action: str, reason: str, who: list[str], urgency: int, window: int, basis: str, needs: list[str], evidence: list[dict], engine: bool = False):
        recs.append({"id": id_, "what_is_happening": reason.split("|")[0].strip(), "why": (reason.split("|") + [""])[1].strip(), "action": action, "who": [GROUPS[x] for x in who],
                     "urgency": URGENCY[urgency], "window": WINDOWS[window], "confidence": _confidence(r, needs, engine=engine, stale=stale), "basis": basis, "evidence": evidence,
                     "_rank": urgency * 10 - window})

    # ---- air quality (CPCB categories) ----
    lvl = aqi["level"]
    if lvl is not None and lvl >= 2:
        cat = aqi["category"]
        ev = [_ev("AQI (PM-based)", aqi["index"], f"CPCB category {cat}", aqi["basis"]), _ev("PM2.5, 24 h average", None if pm25_v is None else round(pm25_v, 1),
              f"CPCB 24-h standard {g.NAAQS_PM25_24H:g} µg/m³; WHO guideline {g.WHO_PM25_24H:g}", "CPCB NAAQS 2009; WHO AQG 2021"),
              _ev("PM10, 24 h average", None if pm10_v is None else round(pm10_v, 1), f"standard {g.NAAQS_PM10_24H:g}; WHO {g.WHO_PM10_24H:g}", "CPCB NAAQS 2009; WHO AQG 2021")]
        stag = (f" Wind is only {wind:.0f} km/h, which limits dispersal." if wind is not None and wind < 8 else "")
        driver = "PM2.5" if aqi["driver"] == "pm25" else "PM10"
        happening = f"Air quality is {cat} (AQI {aqi['index']:.0f}, driven by {driver})."
        why = f"{g.AQI_HEALTH[cat]}{stag}"
        if wind is not None:
            ev.append(_ev("Wind speed", round(wind, 1), "dispersal is weak below about 8 km/h (SYNERA rule of thumb, not an official threshold)", "Open-Meteo"))
        timing = f" Forecast cleanest 3-hour window in the next 24 h: {win['cleanest']} IST (PM2.5 about {win['cleanest_value']:.0f} µg/m³)." if win else ""
        needs = ["pm25", "pm10"]
        u = {"citizen": {2: 0, 3: 1, 4: 2, 5: 3}[lvl], "vulnerable": {2: 1, 3: 2, 4: 2, 5: 3}[lvl], "commute": {2: 0, 3: 1, 4: 2, 5: 2}[lvl], "system": {2: 0, 3: 1, 4: 2, 5: 3}[lvl]}
        if lvl >= 4:
            add("aqi-citizens", "Stay indoors as much as possible, keep windows closed in the dirtiest hours, avoid all outdoor exercise, and use a well-fitted N95/FFP2-type respirator if you must go out (cloth and surgical masks do not stop fine particles)." + timing,
                f"{happening}|{why}", ["citizens"], u["citizen"], 0, "THRESHOLD", needs, ev)
        elif lvl == 3:
            add("aqi-citizens", "Avoid prolonged or strenuous outdoor activity; move exercise indoors, and keep outdoor time short." + timing, f"{happening}|{why}", ["citizens"], u["citizen"], 0, "THRESHOLD", needs, ev)
        else:
            add("aqi-citizens", "Most healthy adults can continue normal activity; consider lighter exercise outdoors." + timing, f"{happening}|{why}", ["citizens"], u["citizen"], 1, "THRESHOLD", needs, ev)
        add("aqi-sensitive", "Keep prescribed reliever medicines within reach, limit exertion outdoors, and follow your doctor's plan; seek care if breathing worsens, or chest tightness or wheeze appears." if lvl >= 3 else
            "Take extra care outdoors: reduce heavy exertion, and keep prescribed medicines with you.", f"{happening}|{g.AQI_HEALTH[cat]}", ["sensitive"], u["vulnerable"], 0, "THRESHOLD", needs, ev)
        add("aqi-schools", ("Move sports, assemblies and breaks indoors; keep children with asthma inside." if lvl == 3 else "Suspend outdoor sports and assemblies; keep children indoors for breaks."
            if lvl >= 4 else "Shorten or lighten outdoor sessions; let children with asthma sit out strenuous activity."), f"{happening}|Children breathe more air for their body weight and are among the groups the CPCB statement names at this level.", ["schools", "children"],
            u["vulnerable"], 1, "THRESHOLD", needs, ev)
        if lvl >= 3:
            add("aqi-commuters", "Avoid long stretches next to heavy traffic, prefer closed-window transport, and shift discretionary trips away from the dirtiest hours" + (f" (forecast dirtiest: {win['dirtiest']} IST)" if win else "") + ".",
                f"{happening}|Pollution is highest near roads and in peak hours.", ["commuters", "outdoor_workers"], u["commute"], 1, "THRESHOLD", needs, ev)
            add("aqi-hospitals", "Review respiratory-care readiness (inhalers, nebulisers, oxygen) and prepare targeted advice for vulnerable patients." + (" Expect more respiratory presentations." if lvl >= 4 else ""),
                f"{happening}|{g.AQI_HEALTH[cat]}", ["hospitals"], u["system"], 2, "THRESHOLD", needs, ev)
            fires = r.get("fires")
            fire_txt = f" Satellite fire detections within about {fires['box_deg']:.1f}° over the last {fires['days']} days: {fires['count']} ({fires['high_confidence']} high confidence)." if fires else ""
            add("aqi-authorities", "Investigate and act on local sources (traffic, construction dust, waste and biomass burning, industry) and activate the city's graded response measures where they exist." + fire_txt,
                f"{happening}|At this level exposure is widespread, not limited to sensitive people.", ["authorities"], u["system"], 1, "THRESHOLD", needs, ev)

    # ---- heat ----
    hi, hic, imd = d["heat_stress_c"], d["heat_index"], d["imd_heat"]
    heat_lvl = hic["level"] if hic else None
    hot = imd["status"] in ("HEAT_WAVE", "SEVERE_HEAT_WAVE")
    if (heat_lvl is not None and heat_lvl >= 2) or hot:
        sev = 3 if (imd["status"] == "SEVERE_HEAT_WAVE" or (heat_lvl or 0) >= 4) else 2 if (hot or (heat_lvl or 0) >= 3) else 1
        ev = [_ev("Heat stress today (larger of heat index now and forecast peak apparent temperature)", None if hi is None else round(hi, 1), f"NWS category {hic['category']}" if hic else None, "NWS heat-index categories"),
              _ev("Forecast maximum temperature", imd.get("tmax_c"), imd["basis"], "IMD heat-wave criteria"), _ev("Departure from normal Tmax", imd.get("departure_c"), "heat wave needs at least 4.5 °C", "IMD / SYNERA climatology 2023-25")]
        happening = f"Heat stress is {hic['category'].lower() if hic else 'elevated'} (heat index {hi:.0f} °C)" + (f"; IMD status: {imd['status'].replace('_', ' ').lower()}" if imd["status"] not in (None, "NORMAL") else "") + "."
        why = "High temperature with humidity limits the body's ability to cool by sweating; risk rises sharply for older adults, children, outdoor workers and people with heart or kidney disease."
        add("heat-citizens", "Avoid outdoor exertion in the hottest hours (roughly 12:00-16:00), drink water regularly before you feel thirsty (oral rehydration salts if sweating heavily), wear light clothing, and never leave anyone in a parked vehicle.",
            f"{happening}|{why}", ["citizens", "sensitive", "children"], sev, 0 if sev >= 2 else 1, "THRESHOLD", ["temperature_c", "humidity_pct"], ev)
        add("heat-workers", "Shift heavy outdoor work to early morning or evening, schedule shaded rest breaks and provide drinking water.", f"{happening}|{why}", ["outdoor_workers", "schools"], sev, 1, "THRESHOLD", ["temperature_c", "humidity_pct"], ev)
        if sev >= 2:
            add("heat-hospitals", "Prepare for heat-related illness (heat exhaustion, heat stroke, dehydration); check cooling and IV-fluid supplies and triage for older and chronically ill patients.", f"{happening}|{why}", ["hospitals", "authorities"], sev, 2, "THRESHOLD", ["temperature_c", "humidity_pct"], ev)

    # ---- rain ----
    rn, rnn = d["rain"], d["rain_next"]
    worst = max([x for x in (rn, rnn) if x], key=lambda x: x["level"], default=None)
    if worst and worst["level"] >= 3:
        mm = max(v for v in (d["rain_24h_mm"], d["rain_next_days_max_mm"]) if v is not None)
        ev = [_ev("Rainfall (24 h so far or forecast daily total)", round(mm, 1), "IMD heavy rainfall: 64.5 mm in 24 h or more", "IMD rainfall categories")]
        add("rain-all", "Avoid low-lying roads and underpasses, do not drive through flooded water, and keep emergency contacts and drainage points clear.", f"{worst['category']} rain ({mm:.0f} mm in a day).|Heavy rain overwhelms drainage and raises the risk of waterlogging and travel disruption; this system does not model flood depth.",
            ["citizens", "commuters", "authorities"], 2 if worst["level"] == 3 else 3, 2, "THRESHOLD", ["precip_mm"], ev)

    # ---- UV ----
    uv = d["uv"]
    if uv and uv["level"] >= 2:
        add("uv", "Limit midday sun, use shade, a hat, sunglasses and sunscreen.", f"UV index up to {d['uv_max']:.0f} ({uv['category']}).|Unprotected skin can burn quickly at these levels.", ["citizens", "children", "schools"], 1 if uv["level"] < 4 else 2, 1, "THRESHOLD",
            ["uv_index"], [_ev("Forecast maximum UV index", d["uv_max"], "WHO/WMO: 6 or more is High", "WHO UV index")])

    # ---- SYNERA engine: Track D (real Indian grid data) ----
    if grid and grid.get("available"):
        top = next((x for x in grid["results"] if x["status"] == "VERIFIED"), grid["results"][0])
        pct = top["state_percentile"]
        if pct is not None and pct >= 0.8 and top["uplift_pp"] is not None and top["uplift_pp"] > 0:           # only when the interaction raises demand
            add("grid-interaction", "Plan for higher-than-usual electricity demand today: line up reserve capacity and demand-response, and keep cooling-related loads (hospitals, water pumping) protected.",
                f"Today's heat and humidity are on the part of the response surface where they push electricity demand above what their separate effects predict (about {top['uplift_pp']:+.1f} percentage points, {pct * 100:.0f}th percentile of {top['state']}'s history).|"
                f"SYNERA found and {top['status'].lower()} a heat x humidity interaction on real Grid-India data (finding {top['finding_id']}, checked on later data).", ["utilities", "authorities"], 1 if pct < 0.95 else 2, 1, "ENGINE", ["temperature_c", "humidity_pct"],
                [_ev("Interaction uplift", round(top["uplift_pp"], 2), "percentage points above the additive expectation", f"SYNERA finding {top['finding_id']}"), _ev("Percentile in the state's history", round(pct * 100), "80th or above triggers this advisory", "Grid-India panel 2019-2024")], engine=False)

    # ---- SYNERA engine: scenario model (US-trained), only when an interaction stands out ----
    # only when the interaction is distinguishable from zero, adds risk, and both conditions are genuinely unusual (at least +1 usual deviation)
    adds = [t for t in (scenario or {}).get("supported_interactions", []) if t["contribution_pct"] > 0 and t["z_a"] >= 1 and t["z_b"] >= 1] if scenario and scenario.get("available") else []
    if adds:
        t = adds[0]
        add("engine-compound", f"Treat days with both {t['label'].replace(' x ', ' and ').lower()} unusual as higher risk for vulnerable people: apply both sets of precautions together.",
            f"The engine's learned {t['label']} interaction adds {t['contribution_pct']:+.2f}% to weekly deaths here (90% range {t['lo_pct']:+.2f} to {t['hi_pct']:+.2f}).|"
            f"This interaction's range excludes zero in the US training data, but only {scenario['model_skill']['interaction_pairs_excluding_zero']} of {scenario['model_skill']['interaction_pairs_tested']} pairs did, against {scenario['model_skill']['expected_by_chance']:.1f} expected by chance.",
            ["citizens", "sensitive", "hospitals"], 1, 2, "ENGINE", ["temperature_c", "pm25"],
            [_ev("Interaction contribution (%)", round(t["contribution_pct"], 3), "90% range must exclude zero", "SYNERA scenario model, 200-replicate bootstrap")], engine=True)

    if not recs:
        recs.append({"id": "all-clear", "what_is_happening": "No official threshold for air quality, heat, rain or UV is currently exceeded in the available data.", "why": "All checked values are inside the lower categories.",
                     "action": "No special precautions are indicated. Keep checking if you are sensitive to air pollution or heat.", "who": [GROUPS["citizens"]], "urgency": URGENCY[0], "window": WINDOWS[0],
                     "confidence": _confidence(r, ["temperature_c", "humidity_pct", "pm25"], stale=stale), "basis": "THRESHOLD", "evidence": [_ev("AQI", aqi["index"], "Good or Satisfactory is 100 or below", "CPCB NAQI")], "_rank": 0})
    recs.sort(key=lambda x: (-x["_rank"], -x["confidence"]["score"]))
    for i, x in enumerate(recs, 1):
        x["rank"] = i
        x.pop("_rank")
    return recs
