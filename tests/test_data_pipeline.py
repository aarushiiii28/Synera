"""Tests for data ingestion and harmonization pipelines."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from synera_core.data.http_client import HTTPClient
from synera_core.data.nasa_power import fetch_power_point
from synera_core.data.openmeteo import fetch_openmeteo_archive

@pytest.fixture
def mock_httpx_client():
    with patch("synera_core.data.http_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance

def test_http_client_cache(tmp_path):
    client = HTTPClient(cache_dir=tmp_path)
    
    with patch.object(client, "_fetch_with_retry") as mock_fetch:
        mock_fetch.return_value = b'{"status": "ok"}'
        
        # First call, should fetch
        content, path, cached = client.get("http://test.com")
        assert not cached
        assert content == b'{"status": "ok"}'
        assert mock_fetch.call_count == 1
        
        # Second call, should use cache
        content2, path2, cached2 = client.get("http://test.com")
        assert cached2
        assert content2 == b'{"status": "ok"}'
        assert mock_fetch.call_count == 1

def test_nasa_power_mock():
    with patch("synera_core.data.http_client.HTTPClient.get_json") as mock_get_json:
        mock_get_json.return_value = ({"properties": {"parameter": {"T2M": {"20230101": 25.0}}}}, Path("fake"), False)
        
        data = fetch_power_point(10.0, 20.0, "20230101", "20230102", ["T2M"])
        assert data["properties"]["parameter"]["T2M"]["20230101"] == 25.0

def test_openmeteo_mock():
    with patch("synera_core.data.http_client.HTTPClient.get_json") as mock_get_json:
        mock_get_json.return_value = ({"daily": {"time": ["2023-01-01"], "temperature_2m_max": [30.5]}}, Path("fake"), False)
        
        data = fetch_openmeteo_archive(10.0, 20.0, "2023-01-01", "2023-01-02", ["temperature_2m_max"], is_daily=True)
        assert data["daily"]["temperature_2m_max"][0] == 30.5
