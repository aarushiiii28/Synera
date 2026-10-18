"""A small synthetic panel with KNOWN effects, used only by tests and the parity fixture (never by the app or the findings).

Six pretend states, 300 weeks each, with a seasonal cycle in every stressor. The outcome is built from planted effects so a test can
check that the fitting code recovers them: PM2.5 raises deaths by ``PM25_EFFECT`` % per usual deviation, ozone by ``O3_EFFECT`` %, and
the PM2.5 x ozone product adds ``PM25_O3_INTERACTION`` % per usual deviation squared.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from synera_core.benchmark.generator import STRESSORS
from synera_core.data.health import national_week_adjust

PM25_EFFECT = 0.6
O3_EFFECT = 0.3
PM25_O3_INTERACTION = 0.4
NOISE_SD = 2.5

_BASE = {"heat_index": (20, 10, 2.5), "pm25": (9, 2, 2.0), "rh": (65, 10, 6.0), "o3": (70, 25, 9.0), "drought_index": (0, 0.5, 1.0),
         "pm10": (22, 5, 5.0), "no2": (20, 6, 4.0), "uv": (3, 2, 0.5), "wind": (16, 3, 3.0), "precip": (2.5, 1.0, 2.0)}


def make_test_panel(n_states: int = 6, n_weeks: int = 300, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2014-01-04", periods=n_weeks, freq="7D")
    doy = dates.dayofyear.to_numpy(float)
    season = np.sin(2 * np.pi * (doy - 110) / 365.25)
    rows = []
    for i in range(n_states):
        cols, anom = {}, {}
        for s in STRESSORS:
            mean, amp, sd = _BASE[s]
            noise = rng.normal(0, sd, n_weeks)
            cols[s] = mean + (i - n_states / 2) * 0.1 * mean + amp * season + noise
            if s in ("precip", "wind", "pm25", "pm10", "o3", "no2", "uv"):
                cols[s] = np.maximum(cols[s], 0.05)
            anom[s] = noise / sd
        y = (PM25_EFFECT * anom["pm25"] + O3_EFFECT * anom["o3"] + PM25_O3_INTERACTION * anom["pm25"] * anom["o3"]
             + rng.normal(0, NOISE_SD, n_weeks))
        df = pd.DataFrame({"city": f"State {chr(65 + i)}", "date": dates, **cols})
        df["outcome_raw"] = y
        df["expected"] = 800.0 + 300.0 * i
        rows.append(df)
    p = pd.concat(rows, ignore_index=True)
    p["outcome"] = national_week_adjust(p["date"], p["outcome_raw"].to_numpy(), p["expected"].to_numpy())
    return p.sort_values(["city", "date"]).reset_index(drop=True)
