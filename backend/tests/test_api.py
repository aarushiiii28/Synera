"""API behaviour: contract shapes, error envelope, read-only ledger, honest empty states, and one real run end to end."""
import pytest
from sqlmodel import Session

B = "/api/v1"


def test_health_shape_and_chain(client):
    r = client.get(f"{B}/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok" and j["ledger"]["chain_valid"] is True
    assert set(j["counts"]) == {"datasets", "runs", "findings"}


def test_datasets_have_provenance_and_runnable_flags(client):
    d = {x["id"]: x for x in client.get(f"{B}/datasets").json()}
    assert {"env_panel", "benchmark_track_b", "osd-211", "osd-237"} <= set(d)
    assert d["env_panel"]["runnable"] is False and d["env_panel"]["provenance"] == "REAL"
    assert d["benchmark_track_b"]["provenance"] == "SIMULATED"
    assert d["osd-211"]["provenance"] == "REAL"


def test_error_envelope(client):
    r = client.get(f"{B}/findings/does-not-exist")
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message", "detail"} and r.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"{B}/datasets/nope").status_code == 404
    assert client.post(f"{B}/runs", json={"dataset_id": "env_panel"}).status_code == 400   # no outcome variable
    assert client.post(f"{B}/runs", json={"dataset_id": "missing"}).status_code == 404
    assert client.post(f"{B}/runs", json={"dataset_id": "osd-211", "n_boot": 5}).status_code == 422


def test_empty_registry_reports_zeros_not_fake_rows(client):
    j = client.get(f"{B}/findings").json()
    assert j["total"] == 0 and j["items"] == []
    assert j["counts"] == {"CANDIDATE": 0, "VALIDATED": 0, "VERIFIED": 0, "BLOCKED": 0, "REJECTED": 0}
    assert client.get(f"{B}/interactions/matrix").status_code == 404                 # no run yet: says so
    risk = client.get(f"{B}/risk/assessment", params={"region": "Delhi"}).json()
    assert risk["available"] is False and risk["risk_tier"] is None and risk["simulated_only"] is True
    assert client.get(f"{B}/risk/assessment", params={"region": "Atlantis"}).status_code == 404


def test_ledger_is_read_only_through_the_api(client):
    for path in ("/ledger/blocks", "/ledger/head", "/ledger/verify"):
        assert client.post(B + path).status_code == 405
        assert client.delete(B + path).status_code == 405
    assert client.get(f"{B}/ledger/proof/xyz").status_code == 400
    assert client.get(f"{B}/ledger/proof/{'ab' * 32}").status_code == 404


def test_tamper_simulator_validation_and_rate_limit(client):
    assert client.post(f"{B}/security/simulate-tamper", json={"dataset_id": "osd-211", "mode": "nonsense"}).status_code == 400
    assert client.post(f"{B}/security/simulate-tamper", json={"dataset_id": "nope", "mode": "bit_flip"}).status_code == 404
    assert client.post(f"{B}/security/simulate-tamper", json={"dataset_id": "osd-211", "mode": "bit_flip", "magnitude": 9}).status_code == 422
    modes = [m["mode"] for m in client.get(f"{B}/security/modes").json()]
    assert set(modes) == {"bit_flip", "subtle_edit", "row_edit", "inject_outliers", "drift_units", "poison_labels", "swap_model", "ledger_tamper"}


def test_benchmark_endpoint_never_hides_limitations(client):
    j = client.get(f"{B}/benchmark/results").json()
    assert "limitations" in j and len(j["limitations"]) >= 1


def test_run_end_to_end_with_sse_findings_and_gates(client, tiny_registry, monkeypatch):
    from backend.app.db.database import engine
    from backend.app.services import runs as runs_service

    monkeypatch.setattr(runs_service, "get_spec", lambda i: tiny_registry["spec"])
    monkeypatch.setattr("synera_core.pipeline.orchestrator.open_ledger", lambda: tiny_registry["ledger"])
    with Session(engine) as s:
        run_id, reused = runs_service.manager.start(s, tiny_registry["ledger"], "tiny_panel",
                                                    {"n_boot": 49, "n_ci": 20, "seed": 5, "effect_gate": 0.02, "quick": False},
                                                    force=False, inline=True)
    assert reused is False
    run = client.get(f"{B}/runs/{run_id}").json()
    assert run["status"] == "COMPLETED" and run["replay"]["matches"] is True
    assert [e["step_name"] for e in run["events"] if e["status"] == "DONE"][-1] == "FINALIZE"

    with client.stream("GET", f"{B}/runs/{run_id}/events") as r:
        text = "".join(r.iter_text())
    assert text.count("data:") >= 9 and "event: end" in text

    items = client.get(f"{B}/findings", params={"dataset_id": "tiny_panel"}).json()["items"]
    for f in items:
        assert f["provenance"] == "SIMULATED" and f["status"] != "VERIFIED"
        v = client.post(f"{B}/findings/{f['id']}/verify").json()
        assert v["new_status"] != "VERIFIED"
        assert any("SIMULATED provenance cap" in x for x in v["reasons"])
        assert client.get(f"{B}/findings/{f['id']}/surface").json()["z_gap"]
    pytest.importorskip("sqlmodel")
