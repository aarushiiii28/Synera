import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from backend.app.main import app
from backend.app.db.database import get_session
from backend.app.db.models import Dataset, Finding

client = TestClient(app)

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_datasets():
    response = client.get("/api/v1/datasets")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_dataset_not_found():
    response = client.get("/api/v1/datasets/nonexistent")
    assert response.status_code == 404

def test_verify_dataset():
    response = client.post("/api/v1/datasets/env_panel/verify")
    assert response.status_code == 200
    assert response.json()["match"] is True

def test_create_run():
    req = {
        "dataset_id": "env_panel",
        "stressor_pairs": "all",
        "methods": ["continuous"],
        "alpha": 0.05,
        "force": True
    }
    response = client.post("/api/v1/runs", json=req)
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    
    # Test getting run
    response = client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200

def test_findings_pagination_sort():
    response = client.get("/api/v1/findings?limit=1&offset=0&sort=-effect_size")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert len(data["items"]) <= 1

def test_finding_verify():
    # Verify a SIMULATED finding (max status VALIDATED)
    response = client.post("/api/v1/findings/find_123/verify")
    assert response.status_code == 200
    assert response.json()["new_status"] == "VALIDATED"

def test_interactions_matrix():
    response = client.get("/api/v1/interactions/matrix?dataset_id=env_panel")
    assert response.status_code == 200
    assert "matrix" in response.json()

def test_benchmark_results():
    response = client.get("/api/v1/benchmark/results")
    assert response.status_code == 200
    assert "fdr_decomposition" in response.json()

def test_simulate_tamper():
    req = {
        "dataset_id": "env_panel",
        "mode": "subtle_edit",
        "magnitude": 0.1
    }
    response = client.post("/api/v1/security/simulate-tamper", json=req)
    assert response.status_code == 200
    assert response.json()["verdict"] == "RESULT BLOCKED FROM VERIFIED STATUS"

def test_risk_assessment():
    response = client.get("/api/v1/risk/assessment?region=Seattle")
    assert response.status_code == 200
    assert response.json()["simulated_only"] is True
    assert response.json()["risk_tier"] == "HIGH"
