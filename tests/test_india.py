"""India live intelligence: thresholds, normalisation and validation, the climatology, the engine integration, the recommendations, and provider failure handling.
No test calls the network: provider payloads are built here in the shape Open-Meteo returns them."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from synera_core.india import climatology as clim
from synera_core.india import engine, guidelines as g, providers, recommend
from synera_core.india.cities import BY_ID, CITIES
from synera_core.india.normalize import build_reading, map_summary


# ---- helpers: Open-Meteo shaped payloads ------------------------------------------------------------------------------
def payloads(pm25=60.0, pm10=100.0, temp=30.0, rh=50.0, wind=10.0, rain_mm_hour=0.0, tmax=34.0, hours=312, now="2026-10-30T12:15"):
    t0 = pd.Timestamp("2026-10-23T00:00")
    times = [(t0 + pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    days = [(t0 + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(hours // 24)]
    n = len(days)
    w = {"current": {"time": now, "temperature_2m": temp, "apparent_temperature": temp + 2, "relative_humidity_2m": rh, "wind_speed_10m": wind, "wind_gusts_10m": wind * 1.5,
                     "wind_direction_10m": 270, "precipitation": 0.0, "surface_pressure": 990.0},
         "hourly": {"time": times, "temperature_2m": [temp] * hours, "relative_humidity_2m": [rh] * hours, "apparent_temperature": [temp + 2] * hours,
                    "precipitation": [rain_mm_hour] * hours, "wind_speed_10m": [wind] * hours},
         "daily": {"time": days, "temperature_2m_max": [tmax] * n, "temperature_2m_min": [temp - 8] * n, "apparent_temperature_max": [tmax + 2] * n, "precipitation_sum": [rain_mm_hour * 24] * n,
                   "uv_index_max": [3.0] * n, "wind_speed_10m_max": [wind + 5] * n}}
    a = {"current": {"time": now, "pm2_5": pm25, "pm10": pm10, "nitrogen_dioxide": 20.0, "sulphur_dioxide": 5.0, "ozone": 40.0, "carbon_monoxide": 300.0, "uv_index": 1.0, "dust": 10.0},
         "hourly": {"time": times, "pm2_5": [pm25] * hours, "pm10": [pm10] * hours, "nitrogen_dioxide": [20.0] * hours, "ozone": [40.0] * hours}}
    return w, a


def history(years=3, seed=0, shift=0.0):
    """Three years of daily 'archive' with an annual cycle and noise."""
    rng = np.random.default_rng(seed)
    d = pd.date_range("2023-01-01", periods=365 * years, freq="D")
    season = np.sin(2 * np.pi * (d.dayofyear - 100) / 365)
    f = lambda base, amp, sd: [float(x) for x in base + amp * season + rng.normal(0, sd, len(d))]   # noqa: E731
    return {"date": [x.strftime("%Y-%m-%d") for x in d], "apparent_temperature_max": f(30 + shift, 8, 2), "temperature_2m_max": f(30, 8, 2), "relative_humidity_2m_mean": f(55, 20, 6),
            "precipitation_sum": [float(x) for x in rng.gamma(0.4, 4, len(d))], "wind_speed_10m_max": f(14, 3, 3), "pm2_5": f(60, 25, 15), "pm10": f(120, 40, 25),
            "ozone": f(45, 10, 8), "nitrogen_dioxide": f(30, 5, 6)}


# ---- thresholds ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pollutant,conc,expected", [("pm25", 0, 0), ("pm25", 30, 50), ("pm25", 60, 100), ("pm25", 90, 200), ("pm25", 120, 300), ("pm25", 250, 400), ("pm25", 380, 500),
                                                     ("pm25", 900, 500), ("pm10", 50, 50), ("pm10", 100, 100), ("pm10", 250, 200), ("pm10", 350, 300), ("pm10", 430, 400)])
def test_cpcb_breakpoints(pollutant, conc, expected):
    assert g.sub_index(pollutant, conc) == pytest.approx(expected, abs=0.1)


def test_aqi_is_the_worst_sub_index_and_never_invents_a_value():
    a = g.national_aqi(45, 300)
    assert a["driver"] == "pm10" and a["category"] == "Poor" and a["level"] == 3
    assert g.national_aqi(None, None)["index"] is None
    assert g.national_aqi(float("nan"), -5)["index"] is None          # impossible values are ignored, not used
    assert g.national_aqi(None, 60)["index"] is not None               # one pollutant is enough for a PM-based index


def test_imd_heat_criteria():
    assert g.imd_heat(41, 5.0, "plains")["status"] == "HEAT_WAVE"
    assert g.imd_heat(41, 2.0, "plains")["status"] == "HOT"            # hot, but the departure criterion is not met
    assert g.imd_heat(46, 1.0, "plains")["status"] == "HEAT_WAVE"      # absolute 45 C
    assert g.imd_heat(41, 7.0, "plains")["status"] == "SEVERE_HEAT_WAVE"
    assert g.imd_heat(31, 5.0, "hills")["status"] == "HEAT_WAVE"
    assert g.imd_heat(38, 5.0, "coastal")["status"] == "HEAT_WAVE"
    assert g.imd_heat(41, None, "plains")["status"] == "HOT" and "departure" in g.imd_heat(41, None)["basis"]
    assert g.imd_heat(None, 5)["status"] is None


def test_rain_uv_heat_index_categories():
    assert g.imd_rain(70)[0] == "Heavy" and g.imd_rain(0)[1] == 0 and g.imd_rain(300)[0] == "Extremely heavy"
    assert g.uv_category(7)[0] == "High" and g.uv_category(11)[0] == "Extreme"
    assert g.heat_index_category(30)[0] == "Caution" and g.heat_index_category(45)[0] == "Danger" and g.heat_index_category(None) is None


def test_composite_risk_is_the_worst_hazard_and_names_it():
    c = g.composite_risk(1, 3, 0)
    assert c["driver"] == "heat" and c["tier"] == "SEVERE"
    assert g.composite_risk(None, None, None)["score"] is None
    assert g.composite_risk(0, 0, 0)["tier"] == "LOW"
    assert g.composite_risk(0, 1, 0)["tier"] == "LOW"                  # heat "Caution" alone is not a risk tier


# ---- normalisation and validation -----------------------------------------------------------------------------------
def test_reading_has_labelled_metrics_and_a_pm_based_aqi():
    w, a = payloads(pm25=100, pm10=150)
    r = build_reading(BY_ID["amritsar"], w, a)
    m = r["metrics"]
    assert m["pm25"]["kind"] == "MODEL_ANALYSIS" and m["pm25"]["source"].startswith("Open-Meteo") and m["pm25"]["unit"] == "µg/m³"
    assert r["derived"]["aqi"]["category"] == "Poor" and r["derived"]["aqi"]["kind"] == "DERIVED"
    assert r["derived"]["aqi"]["note"] and "PM-based" in r["derived"]["aqi"]["note"]
    assert r["quality"]["missing"] == [] and r["quality"]["completeness"] == 1.0
    s = r["series"]
    assert s["now_index"] == 71 and s["time"][s["now_index"]] == "2026-10-30T12:00" and len(s["time"]) == 72 + 72 == len(s["aqi"])      # 3 days back up to the current hour, 3 days ahead


def test_impossible_values_are_dropped_and_reported_not_clipped():
    w, a = payloads()
    w["current"]["relative_humidity_2m"] = 140
    a["current"]["pm2_5"] = -3
    r = build_reading(BY_ID["delhi"], w, a)
    assert r["metrics"]["humidity_pct"]["value"] is None and r["metrics"]["pm25"]["value"] is None
    assert any("outside the physical range" in i for i in r["quality"]["issues"])
    assert "humidity_pct" in r["quality"]["missing"] and r["quality"]["completeness"] < 1


def test_missing_air_quality_means_no_aqi_and_no_invented_pm():
    w, _ = payloads(temp=22, tmax=26)
    r = build_reading(BY_ID["delhi"], w, None)
    assert r["derived"]["aqi"]["index"] is None and r["metrics"]["pm25"]["value"] is None
    assert {"pm25", "pm10", "aqi"} <= set(r["quality"]["missing"])
    s = map_summary(r)
    assert s["aqi"] is None and s["aqi_category"] is None
    recs = recommend.build(r, None, None)
    assert [x["id"] for x in recs] == ["all-clear"] and recs[0]["confidence"]["level"] != "HIGH"     # not claimed with high confidence on partial data


def test_aqi_needs_16_hours_of_the_24():
    w, a = payloads(pm25=100, pm10=150)
    for k in ("pm2_5", "pm10"):                                          # blank the 12 hours up to now
        for i in range(7 * 24, 7 * 24 + 13):
            a["hourly"][k][i] = None
    r = build_reading(BY_ID["delhi"], w, a)
    assert r["derived"]["aqi"]["index"] is None


def test_station_average_overrides_the_model_for_the_index_and_is_labelled():
    w, a = payloads(pm25=30, pm10=50)
    r = build_reading(BY_ID["delhi"], w, a, station={"pm25": 200.0, "pm10": 300.0, "stations": 4, "source": "CPCB", "source_label": "CPCB station average", "time": "2026-10-30 12:00"})
    assert r["derived"]["aqi"]["kind"] == "OBSERVATION" and r["derived"]["aqi"]["category"] in ("Very Poor", "Poor")
    assert r["metrics"]["pm25_station"]["kind"] == "OBSERVATION" and r["metrics"]["pm25"]["kind"] == "MODEL_ANALYSIS"


def test_openaq_is_shown_but_not_used_for_the_24_hour_index():
    w, a = payloads(pm25=45, pm10=70)
    r = build_reading(BY_ID["delhi"], w, a, station={"pm25": 300.0, "pm10": None, "stations": 3, "source": "OpenAQ", "source_label": "OpenAQ", "time": "t"})
    assert r["derived"]["aqi"]["kind"] == "DERIVED" and r["derived"]["aqi"]["category"] == "Satisfactory"
    assert r["metrics"]["pm25_station"]["value"] == 300.0


def test_map_summary_has_what_the_map_needs():
    w, a = payloads(pm25=120, pm10=260, temp=38, rh=40, tmax=41)
    s = map_summary(build_reading(BY_ID["jaipur"], w, a))
    for k in ("id", "name", "lat", "lon", "aqi", "aqi_level", "temperature_c", "humidity_pct", "wind_kmh", "rain_24h_mm", "risk", "risk_tier", "risk_driver", "imd_heat"):
        assert k in s
    assert s["imd_heat"] == "HOT"                                           # 41 C without a normal to compare with: the departure criterion is not applied


def test_city_list_is_consistent():
    assert len({c["id"] for c in CITIES}) == len(CITIES) >= 40
    for name in ("Delhi", "Mumbai", "Bengaluru", "Chennai", "Kolkata", "Hyderabad", "Amritsar", "Chandigarh", "Ludhiana", "Jaipur", "Lucknow", "Pune", "Ahmedabad", "Bhopal", "Patna",
                 "Srinagar", "Dehradun", "Guwahati"):
        assert name.lower() in BY_ID
    assert all(6 < c["lat"] < 37 and 68 < c["lon"] < 98 for c in CITIES)


# ---- climatology ---------------------------------------------------------------------------------------------------
def test_normals_and_anomalies_follow_the_city_not_a_constant():
    h = history()
    today = pd.Timestamp("2026-10-30")
    n = clim.normals(h, today)
    assert {"heat_index", "rh", "pm25", "pm10", "o3", "no2", "wind", "precip"} <= set(n) and n["pm25"]["n"] >= clim.MIN_N and n["_tmax"]["sd"] > 0
    w, a = payloads(pm25=n["pm25"]["mean"], pm10=n["pm10"]["mean"], rh=n["rh"]["mean"], tmax=n["heat_index"]["mean"] - 2)
    live = clim.live_week(w, a, today)
    z, why = clim.anomalies(live, n)
    assert abs(z["pm25"]) < 0.1 and abs(z["pm10"]) < 0.1                       # conditions exactly at the normal are about zero
    w2, a2 = payloads(pm25=n["pm25"]["mean"] + 3 * n["pm25"]["sd"], pm10=n["pm10"]["mean"])
    z2, _ = clim.anomalies(clim.live_week(w2, a2, today), n)
    assert z2["pm25"] == pytest.approx(3.0, abs=0.15)
    assert "uv" in why and "drought_index" in why


def test_too_little_history_gives_no_normal():
    h = {k: v[:25] for k, v in history().items()}
    assert "pm25" not in clim.normals(h, pd.Timestamp("2026-10-30"))


# ---- engine integration (the real scenario model file) -----------------------------------------------------------------
needs_model = pytest.mark.skipif(engine.scenario_model("all") is None, reason="scenario model not built")


@needs_model
def test_scenario_model_runs_on_a_live_reading_and_reports_its_own_weakness():
    today = pd.Timestamp("2026-10-30")
    h = history(seed=1)
    n = clim.normals(h, today)
    w, a = payloads(pm25=n["pm25"]["mean"] + 2.0 * n["pm25"]["sd"], pm10=n["pm10"]["mean"] + 1.5 * n["pm10"]["sd"], tmax=n["heat_index"]["mean"] + 0.5 * n["heat_index"]["sd"])
    r = engine.scenario_for_city(BY_ID["amritsar"], w, a, h, today)
    assert r["available"] and r["lo_pct"] <= r["effect_pct"] <= r["hi_pct"]
    assert r["anomalies"]["pm25"] == pytest.approx(2.0, abs=0.15)
    assert r["contributions"]["pm25"] > 0                                     # more PM2.5 than normal is associated with more deaths in the learned model
    sk = r["model_skill"]
    assert sk["r2_leave_states_out"] < 0.05 and sk["interaction_pairs_tested"] == 45                    # the weak out-of-sample skill is reported, not hidden
    assert "uv" in r["left_at_normal"] and r["caveats"]
    assert r["effect_pct"] == pytest.approx(r["additive_pct"] + r["interaction_pct"], abs=1e-9)


@needs_model
def test_scenario_model_refuses_without_a_climatology():
    w, a = payloads()
    r = engine.scenario_for_city(BY_ID["amritsar"], w, a, None, pd.Timestamp("2026-10-30"))
    assert r["available"] is False and "climatology" in r["reason"]


def fake_finding(gap=0.05):
    n = 30
    return {"id": "f1", "status": "VERIFIED", "provenance": "REAL", "dataset_id": "india_grid", "stressors": ["tmax", "rh"], "type": "NONLINEAR", "evidence_level": "LATER_DATA_REPLICATION",
            "effect": {}, "surface": {"a": "tmax", "b": "rh", "grid_a": np.linspace(10, 46, n).tolist(), "grid_b": np.linspace(20, 100, n).tolist(),
                                      "z_gap": (np.add.outer(np.linspace(0, gap, n), np.zeros(n))).tolist(), "z_additive": [[0] * n] * n, "z_full": [[0] * n] * n}}


def test_grid_stress_reads_the_surface_in_physical_units_where_there_is_history():
    if engine._grid_panel("india_grid") is None:
        pytest.skip("india_grid panel not built")
    r = engine.grid_stress("Delhi", {"tmax": 32.0, "rh": 60.0}, [fake_finding()])
    assert r["available"] and r["results"][0]["days_nearby"] >= engine.SUPPORT_DAYS and r["results"][0]["state_percentile"] is not None
    assert abs(r["results"][0]["uplift_sd"]) <= 0.05 + 1e-9                    # inside the fake surface's range, not an extrapolated number


def test_grid_stress_will_not_read_the_surface_without_history_nearby():
    if engine._grid_panel("india_grid") is None:
        pytest.skip("india_grid panel not built")
    r = engine.grid_stress("Delhi", {"tmax": 55.0, "rh": 5.0}, [fake_finding()])
    assert r["available"] is False and "too few" in r["reason"]


def test_grid_stress_outside_the_panel_states_and_for_unreal_or_unvalidated_findings():
    assert engine.grid_stress("Goa", {"tmax": 30, "rh": 60}, [fake_finding()])["available"] is False
    sim = {**fake_finding(), "provenance": "SIMULATED"}
    cand = {**fake_finding(), "status": "CANDIDATE"}
    assert engine.grid_stress("Delhi", {"tmax": 32, "rh": 60}, [sim, cand])["available"] is False


# ---- recommendations ------------------------------------------------------------------------------------------------
def reading(**kw):
    w, a = payloads(**kw)
    return build_reading(BY_ID["amritsar"], w, a)


def test_severe_air_gives_critical_citizen_advice_with_evidence_and_all_fields():
    r = reading(pm25=300, pm10=480)
    recs = recommend.build(r, None, None)
    top = recs[0]
    assert top["urgency"] == "CRITICAL" and top["basis"] == "THRESHOLD" and [x["rank"] for x in recs] == list(range(1, len(recs) + 1))
    for x in recs:
        for k in ("action", "what_is_happening", "why", "who", "urgency", "window", "confidence", "evidence", "basis"):
            assert x[k], (x["id"], k)
    ids = {x["id"] for x in recs}
    assert {"aqi-citizens", "aqi-sensitive", "aqi-schools", "aqi-commuters", "aqi-hospitals", "aqi-authorities"} <= ids
    assert any("N95" in x["action"] for x in recs)


def test_clean_air_gives_the_all_clear_not_an_invented_warning():
    recs = recommend.build(reading(pm25=10, pm10=20, temp=24, tmax=27), None, None)
    assert [x["id"] for x in recs] == ["all-clear"] and recs[0]["urgency"] == "INFORMATIONAL"


def test_heat_wave_and_heavy_rain_and_uv_rules():
    w, a = payloads(pm25=10, pm10=20, temp=44, rh=35, tmax=46, rain_mm_hour=3.0)
    w["daily"]["uv_index_max"] = [9.0] * len(w["daily"]["time"])
    r = build_reading(BY_ID["jaipur"], w, a, departure_c=6.0)
    ids = {x["id"]: x for x in recommend.build(r, None, None)}
    assert ids["heat-citizens"]["urgency"] in ("HIGH_PRIORITY", "CRITICAL") and "rain-all" in ids and "uv" in ids
    assert "12:00-16:00" in ids["heat-citizens"]["action"]


def test_confidence_drops_with_missing_inputs_and_stale_copies():
    w, a = payloads(pm25=120, pm10=200)
    full = recommend.build(build_reading(BY_ID["delhi"], w, a), None, None)[0]["confidence"]["score"]
    stale = recommend.build(build_reading(BY_ID["delhi"], w, a), None, None, stale=True)[0]["confidence"]["score"]
    w2, a2 = payloads(pm25=120, pm10=200)
    w2["current"]["wind_speed_10m"] = None
    assert stale < full
    r = build_reading(BY_ID["delhi"], w2, a2)
    assert recommend.build(r, None, None)[0]["confidence"]["score"] <= full


def test_engine_recommendation_needs_a_supported_positive_interaction_with_both_conditions_unusual():
    r = reading(pm25=40, pm10=60)
    term = {"a": "heat_index", "b": "pm25", "label": "Heat index x PM2.5", "contribution_pct": 0.2, "lo_pct": 0.05, "hi_pct": 0.35, "supported": True, "z_a": 1.5, "z_b": 1.6}
    skill = {"interaction_pairs_excluding_zero": 7, "interaction_pairs_tested": 45, "expected_by_chance": 4.5}
    scen = {"available": True, "supported_interactions": [term], "interaction_terms": [term], "model_skill": skill}
    ids = [x["id"] for x in recommend.build(r, scen, None)]
    assert "engine-compound" in ids
    for bad in ({**term, "contribution_pct": -0.2}, {**term, "z_a": 0.4}):          # protective, or not both unusual: no advice from the engine
        assert "engine-compound" not in [x["id"] for x in recommend.build(r, {**scen, "supported_interactions": [bad]}, None)]
    assert "engine-compound" not in [x["id"] for x in recommend.build(r, {**scen, "supported_interactions": []}, None)]      # nothing distinguishable from zero
    e = next(x for x in recommend.build(r, scen, None) if x["id"] == "engine-compound")
    assert e["basis"] == "ENGINE" and e["confidence"]["score"] <= 0.45 and "4.5 expected by chance" in e["why"].replace("about ", "")


def test_grid_recommendation_only_when_the_interaction_raises_demand():
    r = reading(pm25=10, pm10=20, temp=36, tmax=40)
    res = {"finding_id": "f", "status": "VERIFIED", "state": "Delhi", "state_percentile": 0.9, "uplift_pp": 1.5, "replication": "LATER_DATA_REPLICATION"}
    assert "grid-interaction" in [x["id"] for x in recommend.build(r, None, {"available": True, "results": [res]})]
    assert "grid-interaction" not in [x["id"] for x in recommend.build(r, None, {"available": True, "results": [{**res, "uplift_pp": -1.5}]})]
    assert "grid-interaction" not in [x["id"] for x in recommend.build(r, None, {"available": True, "results": [{**res, "state_percentile": 0.5}]})]


# ---- providers: failures, retries, cache ------------------------------------------------------------------------------
class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._b, self.headers, self.text = status, body, headers or {}, "x"

    def json(self):
        return self._b


def test_get_retries_after_429_and_5xx_then_succeeds(monkeypatch):
    seq = [Resp(429, headers={"Retry-After": "0"}), Resp(503), Resp(200, {"ok": 1})]
    monkeypatch.setattr(providers.httpx, "get", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    assert providers._get("http://x") == {"ok": 1}


def test_get_gives_up_with_a_readable_error(monkeypatch):
    monkeypatch.setattr(providers.httpx, "get", lambda *a, **k: Resp(500))
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    with pytest.raises(providers.SourceError, match="server error"):
        providers._get("http://x", tries=2)
    monkeypatch.setattr(providers.httpx, "get", lambda *a, **k: Resp(404))
    with pytest.raises(providers.SourceError, match="HTTP 404"):
        providers._get("http://x")


def test_cache_serves_the_last_good_copy_marked_stale_when_the_provider_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(providers, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(providers, "_mem", {})
    v, meta = providers.cached("k1", 60, lambda: {"v": 1})
    assert v == {"v": 1} and meta["status"] == "live"
    v, meta = providers.cached("k1", 60, lambda: {"v": 2})
    assert v == {"v": 1} and meta["status"] == "cached"                      # within the ttl: no second call

    def boom():
        raise providers.SourceError("down")
    v, meta = providers.cached("k1", 0, boom)
    assert v == {"v": 1} and meta["status"] == "stale" and "down" in meta["note"]
    with pytest.raises(providers.SourceError):
        providers.cached("never-fetched", 60, boom)                           # nothing cached: the error is raised, not hidden


def test_optional_providers_say_not_configured_without_keys(monkeypatch):
    for k in ("OPENAQ_API_KEY", "DATA_GOV_IN_API_KEY", "FIRMS_MAP_KEY"):
        monkeypatch.delenv(k, raising=False)
    c = BY_ID["amritsar"]
    for f in (providers.openaq_latest, providers.cpcb_latest, providers.firms_fires):
        v, meta = f(c)
        assert v is None and meta["status"] == "NOT_CONFIGURED"


def test_openaq_parsing_with_a_mocked_api(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAQ_API_KEY", "k")
    monkeypatch.setattr(providers, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(providers, "_mem", {})
    now = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake(url, params=None, headers=None, **k):
        if url.endswith("/v3/locations"):
            return {"results": [{"id": 1, "sensors": [{"id": 11, "parameter": {"name": "pm25"}}, {"id": 12, "parameter": {"name": "pm10"}}]},
                                {"id": 2, "sensors": [{"id": 21, "parameter": {"name": "pm25"}}]}]}
        loc = int(url.split("/")[-2])
        return {"results": [{"sensorsId": 11, "value": 80.0, "datetime": {"utc": now}}, {"sensorsId": 12, "value": 150.0, "datetime": {"utc": now}}] if loc == 1 else
                [{"sensorsId": 21, "value": 120.0, "datetime": {"utc": now}}, {"sensorsId": 21, "value": -999, "datetime": {"utc": now}}]}
    monkeypatch.setattr(providers, "_get", fake)
    v, meta = providers.openaq_latest(BY_ID["amritsar"])
    assert v["pm25"] == pytest.approx(100.0) and v["pm10"] == 150.0 and v["stations"] >= 1 and meta["status"] == "live"       # median of 80 and 120; the -999 is dropped


def test_cpcb_parsing_with_a_mocked_api(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "k")
    monkeypatch.setattr(providers, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(providers, "_mem", {})
    rec = lambda st, p, v: {"station": st, "pollutant_id": p, "pollutant_avg": v, "last_update": "30-10-2026 12:00:00"}   # noqa: E731
    monkeypatch.setattr(providers, "_get", lambda *a, **k: {"records": [rec("A", "PM2.5", "90"), rec("B", "PM2.5", "110"), rec("A", "PM10", "NA"), rec("B", "PM10", "200"), rec("C", "SO2", "5")]})
    v, _ = providers.cpcb_latest(BY_ID["delhi"])
    assert v["pm25"] == 100.0 and v["pm10"] == 200.0 and v["stations"] == 2        # "NA" values and other pollutants are ignored


# ---- service and API --------------------------------------------------------------------------------------------------
def fake_providers(monkeypatch, tmp_path, fail_air=False):
    monkeypatch.setattr(providers, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(providers, "_mem", {})

    def weather(cities):
        return [payloads(pm25=90 + 10 * i, pm10=160)[0] for i, _ in enumerate(cities)], {"status": "live", "fetched_at": 1.0}

    def air(cities):
        if fail_air:
            raise providers.SourceError("air quality down")
        return [payloads(pm25=90 + 10 * i, pm10=160)[1] for i, _ in enumerate(cities)], {"status": "live", "fetched_at": 1.0}
    monkeypatch.setattr(providers, "weather", weather)
    monkeypatch.setattr(providers, "air", air)
    monkeypatch.setattr(providers, "daily_history", lambda city: history(seed=3))
    for f in (providers.openaq_latest, providers.cpcb_latest, providers.firms_fires):
        monkeypatch.setattr(providers, f.__name__, lambda city, _f=f: (None, {"status": "NOT_CONFIGURED", "note": "no key"}))


def test_service_overview_and_city_end_to_end(monkeypatch, tmp_path):
    from synera_core.india import service
    fake_providers(monkeypatch, tmp_path)
    o = service.overview()
    assert o["available"] and len(o["cities"]) == len(CITIES) and {x["id"] for x in o["layers"]} == {"aqi", "temperature", "humidity", "rainfall", "wind", "risk"}
    assert o["national"]["hotspots_air"][0]["value"] >= o["national"]["hotspots_air"][-1]["value"]
    d = service.city_detail("amritsar", [])
    assert d["available"] and d["recommendations"] and d["explain"]["engine"]["grid_findings"]["available"] is False
    assert {s["name"] for s in d["sources"]} >= {"Open-Meteo forecast API", "CPCB via data.gov.in", "OpenAQ", "NASA FIRMS", "IMD"}
    assert next(s for s in d["sources"] if s["name"] == "NASA FIRMS")["status"] == "NOT_CONFIGURED"
    assert d["explain"]["basis_count"]["THRESHOLD"] >= 1 and d["explain"]["not_done"]


def test_service_survives_an_air_quality_outage_without_inventing_values(monkeypatch, tmp_path):
    from synera_core.india import service
    fake_providers(monkeypatch, tmp_path, fail_air=True)
    o = service.overview()
    assert o["available"] and all(c["aqi"] is None and c["pm25"] is None for c in o["cities"]) and o["cities"][0]["temperature_c"] is not None
    d = service.city_detail("delhi", [])
    assert d["available"] and d["derived"]["aqi"]["index"] is None and "aqi" in d["quality"]["missing"]
    assert next(s for s in d["sources"] if "air-quality" in s["name"])["status"] == "ERROR"


def test_service_reports_a_weather_outage_plainly(monkeypatch, tmp_path):
    from synera_core.india import service
    fake_providers(monkeypatch, tmp_path)
    monkeypatch.setattr(providers, "weather", lambda cities: (_ for _ in ()).throw(providers.SourceError("timeout")))
    o = service.overview()
    assert o["available"] is False and "timeout" in o["reason"] and o["cities"] == []
    d = service.city_detail("delhi", [])
    assert d["available"] is False and "No values are shown" in d["reason"]
