"""Health outcome helpers (Track C): turning weekly death counts into an outcome the engine can use.

The REAL panel itself is built by ``scripts/build_health_panel.py`` (CDC NCHS deaths x EPA monitors x ERA5/NASA weather).

Two steps make raw death counts usable, and both exist to stop the analysis from "discovering" things that are only the
calendar:

1. :func:`excess_mortality` removes each state's own trend and annual cycle, leaving the % of deaths above or below what
   that state expects for that week.
2. :func:`national_week_adjust` subtracts the nation's average excess in the same week. Flu waves, heat and cold snaps that
   hit the whole country at once then cannot masquerade as an effect of a local stressor: only differences between
   states in the same week remain (the standard "week fixed effect" of panel studies).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd


# Largest metro area of each state (exposure proxy for the whole state). New York is left out: the CDC series splits
# New York City from the rest of the state, while EPA monitors cannot be split the same way, so exposure would be wrong.
LOCATIONS = {
    "Alabama": (33.52, -86.80), "Alaska": (61.22, -149.90), "Arizona": (33.45, -112.07), "Arkansas": (34.75, -92.29),
    "California": (34.05, -118.24), "Colorado": (39.74, -104.99), "Connecticut": (41.76, -72.67), "Delaware": (39.74, -75.55),
    "District of Columbia": (38.91, -77.04), "Florida": (25.76, -80.19), "Georgia": (33.75, -84.39), "Hawaii": (21.31, -157.86),
    "Idaho": (43.62, -116.20), "Illinois": (41.88, -87.63), "Indiana": (39.77, -86.16), "Iowa": (41.59, -93.62),
    "Kansas": (37.69, -97.34), "Kentucky": (38.25, -85.76), "Louisiana": (29.95, -90.07), "Maine": (43.66, -70.26),
    "Maryland": (39.29, -76.61), "Massachusetts": (42.36, -71.06), "Michigan": (42.33, -83.05), "Minnesota": (44.98, -93.27),
    "Mississippi": (32.30, -90.18), "Missouri": (38.63, -90.20), "Montana": (45.78, -108.50), "Nebraska": (41.26, -95.93),
    "Nevada": (36.17, -115.14), "New Hampshire": (42.99, -71.46), "New Jersey": (40.74, -74.17), "New Mexico": (35.08, -106.65),
    "North Carolina": (35.23, -80.84), "North Dakota": (46.88, -96.79), "Ohio": (39.96, -83.00), "Oklahoma": (35.47, -97.52),
    "Oregon": (45.52, -122.68), "Pennsylvania": (39.95, -75.17), "Rhode Island": (41.82, -71.41), "South Carolina": (34.00, -81.03),
    "South Dakota": (43.55, -96.73), "Tennessee": (36.16, -86.78), "Texas": (29.76, -95.37), "Utah": (40.76, -111.89),
    "Vermont": (44.48, -73.21), "Virginia": (37.54, -77.44), "Washington": (47.61, -122.33), "West Virginia": (38.35, -81.63),
    "Wisconsin": (43.04, -87.91), "Wyoming": (41.14, -104.82),
}


class HealthOutcomeAdapter(ABC):
    """Base interface for health outcome data adapters."""

    @abstractmethod
    def load(self, start_date: str, end_date: str, **kwargs: Any) -> pd.DataFrame:
        """Load health outcome data for a date range.

        Returns a DataFrame with columns ``['date', 'geo_id', 'outcome', 'provenance']``.
        """


def excess_mortality(dates: pd.Series, deaths: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """% excess deaths over the state's own expected level: log deaths ~ linear trend + 3 annual harmonics.

    Returns ``(excess_percent, expected_deaths)``.
    """
    dates = pd.to_datetime(dates)
    t = (dates - dates.iloc[0]).dt.days.to_numpy(float) / 365.25
    doy = dates.dt.dayofyear.to_numpy(float)
    cols = [np.ones_like(t), t]
    for k in (1, 2, 3):
        cols += [np.sin(2 * np.pi * k * doy / 365.25), np.cos(2 * np.pi * k * doy / 365.25)]
    X = np.column_stack(cols)
    y = np.log(deaths.to_numpy(float))
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta
    return 100.0 * (y - fitted), np.exp(fitted)


def weekly_weighted_mean(dates: pd.Series | np.ndarray, values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """For every row, the weight-averaged value of all rows that share its date (here: all states in that week)."""
    df = pd.DataFrame({"d": np.asarray(dates), "v": np.asarray(values, float) * np.asarray(weights, float), "w": np.asarray(weights, float)})
    g = df.groupby("d")[["v", "w"]].transform("sum")
    return (g["v"] / g["w"]).to_numpy()


def national_week_adjust(dates: pd.Series | np.ndarray, values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """``values`` minus the (death-weighted) average of all states in the same week."""
    return np.asarray(values, float) - weekly_weighted_mean(dates, values, weights)
