"""The sensor-interaction analysis: it must detect an interaction that exists, stay quiet when there is none, and refuse when the data cannot tell.

The data here is generated INSIDE THE TEST with a known truth (this is how the engine itself is benchmarked); it says nothing about the physical sensor.
"""
import numpy as np
import pandas as pd

from synera_core.iot.analysis import MIN_ROWS, analyse, binned_means, prepare


def session(n=1500, interaction=0.0, seed=1, t_span=6.0, h_span=20.0, drift=0.0, quality="OK"):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    # slow, autocorrelated temperature and humidity that cross each other's ranges, as in a room
    temp = np.round(24 + t_span / 2 * np.sin(t / 220.0) + rng.normal(0, 0.25, n).cumsum() * 0.02)
    hum = np.round(55 + h_span / 2 * np.sin(t / 170.0 + 1.0) + rng.normal(0, 0.4, n).cumsum() * 0.02)
    zt, zh = (temp - temp.mean()) / (temp.std() + 1e-9), (hum - hum.mean()) / (hum.std() + 1e-9)
    gas = 100 + 4 * zt + 3 * zh + interaction * zt * zh + drift * t / n + rng.normal(0, 2.0, n)
    base = pd.Timestamp("2026-10-30T12:00:00Z")
    return pd.DataFrame({
        "seq": t + 1, "received_utc": [(base + pd.Timedelta(seconds=2 * int(i))).isoformat() for i in t], "device_id": "d", "time_ms": t * 2000,
        "temperature_C": temp, "humidity_pct": hum, "gas_raw": np.round(gas), "temperature_quality": quality, "humidity_quality": quality, "gas_quality": quality,
        "source": "REAL_SENSOR"})


def test_a_planted_interaction_is_detected():
    r = analyse(session(interaction=7.0))
    assert r["kind"] == "EXPLORATORY" and r["status"] == "INTERACTION_DETECTED"
    assert r["result"]["q"] < 0.05 and r["result"]["effect_size_sd"] >= 0.05 and r["result"]["type"] in ("SYNERGISTIC", "ANTAGONISTIC", "NONLINEAR")


def test_no_interaction_is_reported_when_there_is_none():
    wrong = sum(analyse(session(interaction=0.0, seed=s))["status"] == "INTERACTION_DETECTED" for s in range(4))
    assert wrong <= 1                                     # the test is calibrated, not perfect: at most an occasional false alarm


def test_slow_drift_is_not_mistaken_for_an_interaction():
    r = analyse(session(interaction=0.0, drift=40.0, seed=3))
    assert r["data"]["gas_sd_after_detrending"] < 6      # the drift line was removed before the engine saw the data
    assert r["status"] != "INTERACTION_DETECTED"


def test_too_little_data_or_variation_returns_no_result():
    few = analyse(session(n=MIN_ROWS - 50))
    assert few["status"] == "INSUFFICIENT_DATA" and "readings" in few["reasons"][0] and "result" not in few
    flat = analyse(session(t_span=0.5, h_span=1.0))
    assert flat["status"] == "INSUFFICIENT_DATA" and any("temperature" in x for x in flat["reasons"]) and any("humidity" in x for x in flat["reasons"])
    assert "result" not in flat and "advice" in flat


def test_unreliable_readings_are_left_out():
    raw = session(n=800, interaction=7.0)
    raw.loc[:399, "gas_quality"] = "WARMING_UP"
    raw.loc[400:450, "temperature_C"] = np.nan
    p, info = prepare(raw)
    assert info["rows_in_file"] == 800 and len(p) == 349 and info["rows_left_out"] == 451
    assert analyse(session(quality="WARMING_UP"))["status"] == "INSUFFICIENT_DATA"


def test_only_real_sensor_readings_are_analysed():
    raw = session(interaction=7.0)
    raw["source"] = "SIMULATED_TEST"
    assert analyse(raw)["status"] == "INSUFFICIENT_DATA"


def test_the_descriptive_grid_has_no_cells_from_a_handful_of_readings():
    p, _ = prepare(session())
    g = binned_means(p)
    assert len(g["cells"]) == 3 and all(len(r) == 3 for r in g["cells"])
    assert all((c["mean"] is None) == (c["n"] < 20) for r in g["cells"] for c in r)


def test_an_empty_file_is_handled():
    assert analyse(session(n=5).iloc[0:0])["status"] == "INSUFFICIENT_DATA"
