"""India live API routes, with the providers replaced by Open-Meteo-shaped fixtures (no network)."""
from tests.test_india import fake_providers
from synera_core.india.cities import CITIES


def test_api_routes(monkeypatch, tmp_path, client):
    fake_providers(monkeypatch, tmp_path)
    assert len(client.get("/api/v1/india/cities").json()) == len(CITIES)
    o = client.get("/api/v1/india/overview")
    assert o.status_code == 200 and o.json()["available"]
    c = client.get("/api/v1/india/city/amritsar")
    assert c.status_code == 200 and c.json()["recommendations"] and c.json()["city"]["name"] == "Amritsar"
    assert client.get("/api/v1/india/city/atlantis").status_code == 404
