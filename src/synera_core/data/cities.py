"""Benchmark cities and derived environmental variables shared by the data build and the risk module."""

from __future__ import annotations

import numpy as np
import pandas as pd

CITIES: dict[str, dict[str, float]] = {
    "Ludhiana": {"lat": 30.9010, "lon": 75.8523},
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Beijing": {"lat": 39.9042, "lon": 116.4074},
    "Cairo": {"lat": 30.0444, "lon": 31.2357},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
    "Phoenix": {"lat": 33.4484, "lon": -112.0740},
    "Jakarta": {"lat": -6.2088, "lon": 106.8456},
}

START_DATE = "2022-08-01"
END_DATE = "2023-12-31"


def calculate_heat_index(t_c: pd.Series, rh: pd.Series) -> pd.Series:
    """Heat index (deg C) by the Rothfusz regression, valid for T >= 80 F and RH >= 40%.

    Outside that range the simple Steadman-style average is used (documented NWS practice).
    """
    t_f = t_c * 9 / 5 + 32
    simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    rothfusz = (
        -42.379 + 2.04901523 * t_f + 10.14333127 * rh
        - 0.22475541 * t_f * rh - 6.83783e-3 * t_f ** 2
        - 5.481717e-2 * rh ** 2 + 1.22874e-3 * t_f ** 2 * rh
        + 8.5282e-4 * t_f * rh ** 2 - 1.99e-6 * t_f ** 2 * rh ** 2
    )
    hi = np.where((t_f >= 80) & (rh >= 40), rothfusz, simple)
    return pd.Series((hi - 32) * 5 / 9, index=t_c.index)
