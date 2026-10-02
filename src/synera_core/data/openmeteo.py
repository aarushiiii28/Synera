"""Open-Meteo API ingestion client for meteorological and air quality metrics."""

from __future__ import annotations

from typing import Any

import httpx


def fetch_openmeteo_archive(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: list[str],
) -> dict[str, Any]:
    """Fetch historical weather or air quality metrics from Open-Meteo archive.

    Args:
        latitude: Target latitude.
        longitude: Target longitude.
        start_date: ISO start date string (YYYY-MM-DD).
        end_date: ISO end date string (YYYY-MM-DD).
        variables: List of hourly or daily meteorological variables to retrieve.

    Returns:
        JSON response dictionary from the Open-Meteo endpoint.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get("https://archive-api.open-meteo.com/v1/archive", params=params)
        response.raise_for_status()
        return response.json()
