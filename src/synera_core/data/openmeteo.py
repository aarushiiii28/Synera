"""Open-Meteo API ingestion client for meteorological and air quality metrics."""

from __future__ import annotations

from typing import Any

from synera_core.data.http_client import HTTPClient


def fetch_openmeteo_archive(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: list[str],
    is_daily: bool = False,
) -> dict[str, Any]:
    """Fetch historical weather metrics from Open-Meteo archive.

    Args:
        latitude: Target latitude.
        longitude: Target longitude.
        start_date: ISO start date string (YYYY-MM-DD).
        end_date: ISO end date string (YYYY-MM-DD).
        variables: List of hourly or daily meteorological variables to retrieve.
        is_daily: True if variables are daily rather than hourly.

    Returns:
        JSON response dictionary from the Open-Meteo endpoint.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "auto"
    }
    if is_daily:
        params["daily"] = ",".join(variables)
    else:
        params["hourly"] = ",".join(variables)
        
    client = HTTPClient()
    data, _, _ = client.get_json("https://archive-api.open-meteo.com/v1/archive", params=params)
    return data


def fetch_openmeteo_air_quality(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: list[str],
) -> dict[str, Any]:
    """Fetch air quality metrics from Open-Meteo API.

    Args:
        latitude: Target latitude.
        longitude: Target longitude.
        start_date: ISO start date string (YYYY-MM-DD).
        end_date: ISO end date string (YYYY-MM-DD).
        variables: List of hourly air quality variables.

    Returns:
        JSON response dictionary.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "auto"
    }
    client = HTTPClient()
    data, _, _ = client.get_json("https://air-quality-api.open-meteo.com/v1/air-quality", params=params)
    return data
