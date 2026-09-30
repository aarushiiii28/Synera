"""NASA POWER (Prediction of Worldwide Energy Resources) API client.

Retrieves solar, meteorological, and radiation climatology datasets.
"""

from __future__ import annotations

from typing import Any, Dict, List
import httpx


def fetch_power_point(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    parameters: List[str],
    community: str = "AG",
) -> Dict[str, Any]:
    """Fetch point climatology or agroclimatology data from NASA POWER API.

    Args:
        latitude: Target decimal latitude.
        longitude: Target decimal longitude.
        start_date: Formatted YYYYMMDD string.
        end_date: Formatted YYYYMMDD string.
        parameters: List of NASA POWER parameter codes (e.g. ALLSKY_SFC_SW_DWN).
        community: Community tag ('AG' for agroclimatology, 'SB' for sustainable buildings).

    Returns:
        JSON response payload.
    """
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": ",".join(parameters),
        "community": community,
        "longitude": longitude,
        "latitude": latitude,
        "start": start_date,
        "end": end_date,
        "format": "JSON",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()
