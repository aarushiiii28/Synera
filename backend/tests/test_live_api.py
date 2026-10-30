"""Live Stress Lab API, with a fake serial port and a temporary ledger. Nothing here proves the physical Arduino works: that is checked by hand and in e2e/live.cjs."""
import time

import pytest

from synera_core.iot.bridge import SerialBridge

LINES = ["# device=synera-uno-dht11-mq", "time_ms,temperature_C,humidity_pct,gas_raw", "1000,26.0,57.0,400", "3000,26.1,58.0,402", "5000,,,401"]


class FakePort:
    def __init__(self):
        self.lines = list(LINES)

    def readline(self):
        time.sleep(0.01)
        if not self.lines:
            time.sleep(0.2)
            return b""
        return (self.lines.pop(0) + "\n").encode()

    def close(self):
        pass


@pytest.fixture()
def bridge(client, tmp_path):
    from backend.app import main
    from backend.app.core.deps import get_bridge
    b = SerialBridge(tmp_path / "live", opener=lambda p, r: FakePort(), warmup_s=0, retry_s=0.1, no_data_timeout_s=1.0)
    main.app.dependency_overrides[get_bridge] = lambda: b
    yield b
    b.disconnect()
    main.app.dependency_overrides.pop(get_bridge, None)


def wait(cond, t=5.0):
    end = time.time() + t
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_not_connected_means_no_readings_and_an_honest_status(client, bridge):
    s = client.get("/api/v1/live/status").json()
    assert s["state"] == "DISCONNECTED" and s["packets_ok"] == 0 and s["receiving"] is False
    r = client.get("/api/v1/live/readings").json()
    assert r["items"] == [] and r["latest_seq"] == 0


def test_ports_and_spec_explain_the_limits(client, bridge):
    p = client.get("/api/v1/live/ports").json()
    assert isinstance(p["ports"], list) and 9600 in p["bauds"]
    sp = client.get("/api/v1/live/spec").json()
    assert sp["format"] == "time_ms,temperature_C,humidity_pct,gas_raw" and any("not ppm" in n for n in sp["notes"])


def test_connect_streams_real_sensor_readings_with_provenance_and_missing_values(client, bridge):
    s = client.post("/api/v1/live/connect", json={"port": "COM_FAKE", "baud": 9600}).json()
    assert s["port"] == "COM_FAKE"
    assert wait(lambda: client.get("/api/v1/live/status").json()["packets_ok"] == 3)
    items = client.get("/api/v1/live/readings").json()["items"]
    assert [i["source"] for i in items] == ["REAL_SENSOR"] * 3
    m = {x["sensor"]: x for x in items[0]["measurements"]}
    assert m["temperature"]["unit"] == "°C" and m["gas"]["quality"] == "OK" and "calibrated" not in m["gas"]["unit"]
    last = {x["sensor"]: x for x in items[2]["measurements"]}
    assert last["temperature"]["value"] is None and last["temperature"]["quality"] == "MISSING"      # reported missing, not guessed
    assert client.get("/api/v1/live/readings", params={"after": items[0]["seq"]}).json()["items"][0]["seq"] == items[1]["seq"]
    d = client.post("/api/v1/live/disconnect").json()
    assert d["state"] == "DISCONNECTED"


def test_a_bad_baud_or_port_name_is_a_client_error(client, bridge):
    assert client.post("/api/v1/live/connect", json={"port": "COM_FAKE", "baud": 1234}).status_code == 400
    assert client.post("/api/v1/live/connect", json={"port": "", "baud": 9600}).status_code == 422


def test_the_simulated_feed_is_labelled_and_refused_while_hardware_is_connected(client, bridge):
    s = client.post("/api/v1/live/test-mode/start").json()
    assert s["state"] == "TEST_MODE" and s["source"] == "SIMULATED_TEST"
    assert wait(lambda: client.get("/api/v1/live/readings").json()["items"] != [])
    assert {i["source"] for i in client.get("/api/v1/live/readings").json()["items"]} == {"SIMULATED_TEST"}
    client.post("/api/v1/live/test-mode/stop")
    client.post("/api/v1/live/connect", json={"port": "COM_FAKE", "baud": 9600})
    assert wait(lambda: client.get("/api/v1/live/status").json()["packets_ok"] >= 1)
    assert client.post("/api/v1/live/test-mode/start").status_code == 409


def test_sealing_records_the_session_file_in_the_ledger(client, bridge, tmp_ledger):
    assert client.post("/api/v1/live/seal").status_code == 404                     # nothing to seal yet
    client.post("/api/v1/live/connect", json={"port": "COM_FAKE", "baud": 9600})
    assert wait(lambda: client.get("/api/v1/live/status").json()["packets_ok"] == 3)
    sealed = client.post("/api/v1/live/seal").json()
    assert sealed["sealed"] and sealed["rows"] == 3 and len(sealed["sha256"]) == 64
    assert tmp_ledger.get(sealed["ledger_block"]).payload["provenance"] == "REAL_SENSOR"
    assert tmp_ledger.verify()["valid"]


def test_analysis_needs_a_hardware_session_and_refuses_thin_data(client, bridge, tmp_path):
    assert client.post("/api/v1/live/analyze").status_code == 404                     # nothing collected yet
    client.post("/api/v1/live/connect", json={"port": "COM_FAKE", "baud": 9600})
    assert wait(lambda: client.get("/api/v1/live/status").json()["packets_ok"] == 3)
    r = client.post("/api/v1/live/analyze").json()                                      # three readings are far too few
    assert r["status"] == "INSUFFICIENT_DATA" and r["kind"] == "EXPLORATORY" and "result" not in r and r["reasons"]


def test_analysis_runs_the_engine_on_a_long_session_and_calls_it_exploratory(client, bridge, tmp_path):
    from tests.test_iot_analysis import session
    path = tmp_path / "session_test.csv"
    session(n=1200, interaction=7.0).to_csv(path, index=False)                          # data generated in the test with a planted interaction
    bridge._last_session = {"file": path.name, "rows": 1200, "path": str(path), "sealed": False}
    r = client.post("/api/v1/live/analyze").json()
    assert r["kind"] == "EXPLORATORY" and r["status"] == "INTERACTION_DETECTED" and r["result"]["q"] < 0.05
    assert any("not a validated" in x for x in r["limits"]) and len(r["grid"]["cells"]) == 3


def test_history_compares_with_real_outdoor_data_and_states_the_caveats(client, bridge):
    from synera_core.pipeline.registry import get_spec
    if not get_spec("env_panel").abs_path.exists():
        pytest.skip("env_panel is not available")
    h = client.get("/api/v1/live/history", params={"city": "Ludhiana", "temperature": 26, "humidity": 57}).json()
    assert h["dataset"]["provenance"] == "REAL" and h["dataset"]["id"] == "env_panel"
    assert 0 <= h["temperature"]["percentile_of_reading"] <= 100 and h["humidity"]["n_days"] > 100
    assert any("not like-for-like" in c for c in h["caveats"])
    assert client.get("/api/v1/live/history", params={"city": "Atlantis"}).status_code == 404
