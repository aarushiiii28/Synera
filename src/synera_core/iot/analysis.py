"""Does the gas sensor respond to temperature and humidity TOGETHER? The live data, run through the unchanged interaction engine.

MQ-series gas sensors are known to be cross-sensitive to temperature and humidity, so the question has a real answer in the data the Arduino collects:
stressors = temperature and humidity (DHT11), response = the gas reading. The engine is the same one used on the real health and electricity data
(``synera_core.discovery.stack.run_full_stack``), with its pre-set rules and block-bootstrap-calibrated test.

What this is, and is not:

* It is an **exploratory** analysis of one device over one session: one pair of stressors, a few hours of autocorrelated readings from one room.
  Nothing here can become a validated or verified finding (the registry's gates need replication), and the second-opinion models are not run because with a
  single pair their agreement would mean nothing.
* The gas reading is detrended first (linear and quadratic in time): an MQ sensor drifts for a long time after power-up, and without this the
  drift, not the weather, would be "found". Readings flagged WARMING_UP, MISSING or out of range are left out.
* If temperature or humidity barely varied, the analysis says so and returns nothing, instead of a number.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from synera_core.discovery.stack import run_full_stack

STRESSORS = ["temperature", "humidity"]
MIN_ROWS = 300            # about ten minutes of readings
MIN_T_RANGE = 2.0         # degrees C that temperature must span (the DHT11 reports whole degrees)
MIN_RH_RANGE = 6.0        # percent that humidity must span
MIN_T_SD = 0.3            # degrees C of movement that must remain after the slow trend is removed
MIN_RH_SD = 1.0           # percent
MAX_ROWS = 4000           # the newest readings only: keeps the run to seconds


def load_session(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def prepare(raw: pd.DataFrame, max_rows: int = MAX_ROWS) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Usable readings as an engine panel, plus what was dropped and why."""
    n_all = int(len(raw))
    d = raw.copy()
    d = d[d["source"] == "REAL_SENSOR"]
    ok = (d["temperature_quality"] == "OK") & (d["humidity_quality"] == "OK") & (d["gas_quality"] == "OK")
    d = d[ok].dropna(subset=["temperature_C", "humidity_pct", "gas_raw"]).copy()
    d["date"] = pd.to_datetime(d["received_utc"], utc=True).dt.tz_localize(None)
    d = d.sort_values("date").drop_duplicates("date").tail(max_rows).reset_index(drop=True)
    info = {"rows_in_file": n_all, "rows_used": int(len(d)), "rows_left_out": n_all - int(len(d))}
    if len(d) == 0:
        return d, info
    t = (d["date"] - d["date"].iloc[0]).dt.total_seconds().to_numpy() / 3600.0
    gas = d["gas_raw"].to_numpy(float)
    X = np.column_stack([np.ones_like(t), t, t * t])

    def detrend(v: np.ndarray) -> np.ndarray:
        """What is left of ``v`` after removing a quadratic in time (the same basis for all three series)."""
        return v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
    # Temperature and humidity are detrended too (Frisch-Waugh): if only the gas value were, a slow trend shared by the stressors would leave behind a
    # curved, non-additive leftover that the engine would read as an interaction. The question left is about the faster ups and downs.
    temp_d = d["temperature_C"].to_numpy(float) - float(d["temperature_C"].mean())
    hum_d = d["humidity_pct"].to_numpy(float) - float(d["humidity_pct"].mean())
    t_res, h_res, g_res = detrend(temp_d), detrend(hum_d), detrend(gas)
    # The engine orders its panels by a daily date. Readings come every few seconds, so the observation ORDER is passed as consecutive pseudo-days; the
    # engine uses it only for ordering and for the block bootstrap (blocks are counted in observations). Its annual-cycle terms then absorb any
    # 365-observation cycle, which is harmless here. The real timestamps stay in the `time` column.
    panel = pd.DataFrame({"city": "arduino", "date": pd.Timestamp("2000-01-01") + pd.to_timedelta(np.arange(len(d)), unit="D"), "time": d["date"],
                          "temperature": t_res, "humidity": h_res, "outcome": g_res, "temperature_raw": d["temperature_C"].to_numpy(float),
                          "humidity_raw": d["humidity_pct"].to_numpy(float), "gas_raw": gas})
    info.update(hours=float(t[-1]), temperature_range=[float(d["temperature_C"].min()), float(d["temperature_C"].max())],
                humidity_range=[float(d["humidity_pct"].min()), float(d["humidity_pct"].max())], gas_sd_after_detrending=float(panel["outcome"].std()),
                temperature_sd_after_detrending=float(t_res.std()), humidity_sd_after_detrending=float(h_res.std()))
    return panel, info


def sufficiency(panel: pd.DataFrame, info: dict[str, Any]) -> list[str]:
    why = []
    if len(panel) < MIN_ROWS:
        why.append(f"only {len(panel)} usable readings so far; at least {MIN_ROWS} are needed (about ten minutes of clean data after the gas sensor warms up)")
    t0, t1 = info["temperature_range"]
    h0, h1 = info["humidity_range"]
    if t1 - t0 < MIN_T_RANGE:
        why.append(f"temperature only varied from {t0:.0f} to {t1:.0f} °C; it must span at least {MIN_T_RANGE:g} °C")
    if h1 - h0 < MIN_RH_RANGE:
        why.append(f"humidity only varied from {h0:.0f} to {h1:.0f} %; it must span at least {MIN_RH_RANGE:g} %")
    if panel["temperature_raw"].nunique() < 3 or panel["humidity_raw"].nunique() < 3:
        why.append("temperature or humidity took fewer than three different values")
    if info["temperature_sd_after_detrending"] < MIN_T_SD or info["humidity_sd_after_detrending"] < MIN_RH_SD:
        why.append("once the slow trend is removed, temperature or humidity barely moves: the readings need faster ups and downs to test a response")
    return why


def binned_means(panel: pd.DataFrame, bins: int = 3) -> dict[str, Any]:
    """Mean detrended gas reading in a 3 x 3 grid of temperature and humidity (a plain description of the data, not a model)."""
    tq = pd.qcut(panel["temperature"].rank(method="first"), bins, labels=False)
    hq = pd.qcut(panel["humidity"].rank(method="first"), bins, labels=False)
    cells = []
    for i in range(bins):
        row = []
        for j in range(bins):
            m = (tq == i) & (hq == j)
            n = int(m.sum())
            row.append({"n": n, "mean": float(panel.loc[m, "outcome"].mean()) if n >= 20 else None})
        cells.append(row)
    t_edges = [float(panel.loc[tq == i, "temperature"].min()) for i in range(bins)] + [float(panel["temperature"].max())]
    h_edges = [float(panel.loc[hq == j, "humidity"].min()) for j in range(bins)] + [float(panel["humidity"].max())]
    return {"cells": cells, "temperature_edges": t_edges, "humidity_edges": h_edges,
            "unit": "gas counts above (+) or below (-) the drift line; temperature and humidity are relative to their own slow trend"}


def analyse(raw: pd.DataFrame, quick: bool = True, seed: int = 20260929) -> dict[str, Any]:
    panel, info = prepare(raw)
    out: dict[str, Any] = {"kind": "EXPLORATORY", "question": "Does the gas sensor's reading depend on temperature and humidity together?", "data": info,
                           "limits": ["One device, one room, one session: an exploratory result, not a validated or verified finding.",
                                      "The gas value is detrended in time first, because MQ sensors drift for hours after power-up.",
                                      "Readings are autocorrelated; the engine's block bootstrap accounts for that, and the test is slightly anti-conservative.",
                                      "The second-opinion models are not run: with one pair of stressors their agreement would mean nothing."]}
    why = sufficiency(panel, info) if len(panel) else ["no usable readings yet"]
    if why:
        out.update(status="INSUFFICIENT_DATA", reasons=why,
                   advice="Keep logging, and let temperature and humidity vary: breathe near the DHT11, open a window, or warm the room for a while. Then run it again.")
        return out
    res = run_full_stack(panel, "outcome", STRESSORS, alpha=0.05, effect_gate=0.05, n_boot=99 if quick else 299, n_ci=60 if quick else 200, seed=seed, topk=6,
                         second_opinion=False)
    r = res["pairs"][0]
    detected = bool(r["s3_conditional"] and r.get("s4_effect"))
    xs = panel[STRESSORS].to_numpy(float)
    z = (xs - xs.mean(0)) / xs.std(0)
    slope = np.linalg.lstsq(np.column_stack([np.ones(len(z)), z]), panel["outcome"].to_numpy(float), rcond=None)[0][1:]
    sd = float(panel["outcome"].std())
    out.update(
        status="INTERACTION_DETECTED" if detected else "NO_INTERACTION_DETECTED",
        result={"p_calibrated": float(r["p_boot"]), "q": float(r["q_boot"]), "p_naive": float(r["p_naive"]), "type": r.get("type") if detected else None,
                "effect_size_sd": r.get("effect_size"), "effect_ci": [r.get("eff_ci_low"), r.get("eff_ci_high")], "alpha": 0.05, "effect_gate_sd": 0.05,
                "block_length": res["block_len"], "n": int(res["n_rows"])},
        main_effects={"per_1sd_temperature": float(slope[0]), "per_1sd_humidity": float(slope[1]), "unit": "gas counts per one standard deviation of the stressor, descriptive only",
                      "temperature_sd": float(xs[:, 0].std()), "humidity_sd": float(xs[:, 1].std())},
        grid=binned_means(panel), outcome_sd=sd)
    return out
