"""Live Stress Lab core: packet parsing, validation, the serial bridge state machine (with a fake port), the test feed and session sealing.

No physical Arduino is needed here, and nothing in this file claims the hardware works: the fake port only exercises the software.
"""
import threading
import time

import pytest

from synera_core.iot.bridge import CONNECTED, DISCONNECTED, ERROR, RECONNECTING, TEST_MODE, SerialBridge, list_ports
from synera_core.iot.readings import (
    MISSING, OK, OUT_OF_SPEC, SOURCE_REAL, SOURCE_TEST, WARMING_UP, ParseError, build_reading, is_noise, parse_line,
)
from synera_core.provenance.ledger import Ledger


# ------------------------------------------------------------------------------------------------ parsing
def test_a_valid_line_is_parsed_with_units_and_quality():
    t, parsed = parse_line("2000,26.5,57.0,412")
    r = build_reading(1, "dev", t, parsed)
    assert t == 2000 and r.source == SOURCE_REAL
    assert {m.sensor: (m.value, m.unit, m.quality) for m in r.measurements} == {
        "temperature": (26.5, "°C", OK), "humidity": (57.0, "%", OK), "gas": (412.0, "ADC counts (0-1023)", OK)}


def test_a_missing_dht_value_stays_missing_and_is_never_replaced():
    t, parsed = parse_line("4000,,,67")
    r = build_reading(2, "dev", t, parsed)
    assert r.value("temperature") is None and r.value("humidity") is None and r.value("gas") == 67.0
    assert [m.quality for m in r.measurements] == [MISSING, MISSING, OK]


@pytest.mark.parametrize("line,why", [
    ("", "expected 4"), ("1,2,3", "expected 4"), ("1,2,3,4,5", "expected 4"),
    ("abc,26,57,400", "time_ms"), ("1000,hot,57,400", "temperature_C"), ("1000,26,wet,400", "humidity_pct"), ("1000,26,57,x", "gas_raw"),
    ("1000,26,57,", "gas_raw is missing"), ("-5,26,57,400", "non-negative"), ("1000,26,57,400.5", "whole number"),
    ("1000,200,57,400", "physically possible"), ("1000,26,150,400", "physically possible"), ("1000,26,57,2000", "physically possible"),
    ("1000,nan,57,400", "not finite"), ("1000,inf,57,400", "not finite"),
])
def test_invalid_lines_are_rejected_with_a_reason(line, why):
    with pytest.raises(ParseError) as e:
        parse_line(line)
    assert why in e.value.reason


def test_values_outside_the_sensor_specification_are_kept_but_flagged():
    _, parsed = parse_line("1000,55,95,400")           # possible in the world, outside what a DHT11 is rated for
    q = {s: ql for s, _, ql in parsed}
    assert q["temperature"] == OUT_OF_SPEC and q["humidity"] == OUT_OF_SPEC and q["gas"] == OK


def test_comments_and_the_header_are_not_data():
    assert is_noise("# device=synera-uno-dht11-mq") and is_noise("time_ms,temperature_C,humidity_pct,gas_raw") and is_noise("  ")
    assert not is_noise("1000,26,57,400")


def test_gas_is_flagged_while_the_sensor_warms_up():
    _, parsed = parse_line("1000,26,57,400")
    assert build_reading(1, "d", 1000, parsed, warming_up=True).measurements[2].quality == WARMING_UP
    assert build_reading(1, "d", 1000, parsed, warming_up=False).measurements[2].quality == OK


# ------------------------------------------------------------------------------------------------ the bridge, with a fake serial port
class FakePort:
    def __init__(self, lines, die_after=None):
        self.lines, self.die_after, self.closed, self.n = list(lines), die_after, False, 0

    def readline(self):
        if self.die_after is not None and self.n >= self.die_after:
            raise OSError("device unplugged")
        time.sleep(0.01)
        if not self.lines:
            time.sleep(0.2)
            return b""
        self.n += 1
        return (self.lines.pop(0) + "\n").encode()

    def close(self):
        self.closed = True


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def make(tmp_path, opener, **kw):
    return SerialBridge(tmp_path, opener=opener, retry_s=0.1, no_data_timeout_s=0.6, **kw)


GOOD = ["# device=synera-uno-dht11-mq", "time_ms,temperature_C,humidity_pct,gas_raw", "1000,26.0,57.0,400", "3000,26.1,57.0,402", "garbage line", "5000,26.1,58.0,401"]


def test_connected_means_valid_packets_arrived_and_bad_lines_are_counted(tmp_path):
    b = make(tmp_path, lambda p, r: FakePort(GOOD), warmup_s=0)
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["packets_ok"] == 3)
    s = b.status()
    assert s["state"] == CONNECTED and s["packets_rejected"] == 1 and s["device_id"] == "synera-uno-dht11-mq"
    items = b.readings()
    assert [i["seq"] for i in items] == [1, 2, 3] and all(i["source"] == SOURCE_REAL for i in items)
    b.disconnect()
    assert b.status()["state"] == DISCONNECTED
    assert b.readings() == []                           # nothing from the old session lingers on a disconnected lab


def test_a_port_that_opens_but_stays_silent_is_not_connected(tmp_path):
    b = make(tmp_path, lambda p, r: FakePort([]))
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["state"] == ERROR, 3.0)
    s = b.status()
    assert s["packets_ok"] == 0 and b.readings() == [] and "no valid data" in s["last_error"]
    b.disconnect()


def test_an_open_failure_reports_the_reason_and_the_ide_hint(tmp_path):
    def opener(p, r):
        raise PermissionError("could not open port 'COM_FAKE': Access is denied.")
    b = make(tmp_path, opener)
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["state"] == ERROR)
    assert "Serial Monitor" in b.status()["last_error"]
    b.disconnect()


def test_unplugging_gives_reconnecting_and_never_fabricates_readings(tmp_path):
    ports = []

    def opener(p, r):
        ports.append(FakePort(GOOD, die_after=4) if not ports else FakePort([]))      # dies after the comment, the header and two readings
        return ports[-1]
    b = make(tmp_path, opener, warmup_s=0)
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["state"] == RECONNECTING)
    n = len(b.readings())
    time.sleep(0.5)
    assert len(b.readings()) == n and n == 2          # nothing was invented while the device was gone
    assert len(ports) >= 2 and ports[0].closed        # the old port was closed and it tried again
    b.disconnect()


def test_the_history_is_bounded(tmp_path):
    lines = [f"{1000 * i},26.0,57.0,{400 + i % 5}" for i in range(1, 80)]
    b = make(tmp_path, lambda p, r: FakePort(lines), warmup_s=0, buffer_size=20)
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["packets_ok"] == 79)
    assert len(b.readings(limit=2000)) == 20 and b.readings()[-1]["seq"] == 79
    b.disconnect()


def test_a_bad_baud_rate_is_refused(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path, lambda p, r: FakePort([])).connect("COM1", 1234)


# ------------------------------------------------------------------------------------------------ the labelled test feed
def test_the_test_feed_is_labelled_and_cannot_run_with_hardware(tmp_path):
    b = make(tmp_path, lambda p, r: FakePort(GOOD), warmup_s=0)
    s = b.start_test(rate_hz=50)
    assert s["state"] == TEST_MODE and s["source"] == SOURCE_TEST and s["test_mode"] and "SIMULATED" in s["message"]
    assert wait_for(lambda: len(b.readings()) >= 3)
    assert {r["source"] for r in b.readings()} == {SOURCE_TEST} and b.status()["session"] is None     # never written as evidence
    b.disconnect()
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["packets_ok"] >= 1)
    with pytest.raises(RuntimeError):
        b.start_test()
    b.disconnect()


def test_switching_between_test_and_hardware_never_mixes_the_history(tmp_path):
    b = make(tmp_path, lambda p, r: FakePort(GOOD), warmup_s=0)
    b.start_test(rate_hz=50)
    assert wait_for(lambda: len(b.readings()) >= 2)
    b.disconnect()
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["packets_ok"] == 3)
    assert {r["source"] for r in b.readings()} == {SOURCE_REAL}
    b.disconnect()


# ------------------------------------------------------------------------------------------------ evidence
def test_a_real_session_is_written_to_a_file_and_sealed_in_the_ledger(tmp_path):
    b = make(tmp_path / "live", lambda p, r: FakePort(GOOD), warmup_s=0)
    b.connect("COM_FAKE", 9600)
    assert wait_for(lambda: b.status()["packets_ok"] == 3)
    ledger = Ledger(tmp_path / "l.db", tmp_path / "k.pem")
    sealed = b.seal_last_session(ledger)
    assert sealed["sealed"] and sealed["rows"] == 3 and len(sealed["sha256"]) == 64
    blk = ledger.get(sealed["ledger_block"])
    assert blk.payload["provenance"] == "REAL_SENSOR" and sealed["sha256"] in blk.payload["artifact_hashes"] and ledger.verify()["valid"]
    text = (tmp_path / "live" / sealed["file"]).read_text()
    assert text.splitlines()[0].startswith("seq,received_utc") and text.count("REAL_SENSOR") == 3
    assert b.seal_last_session(ledger)["sealed"]       # sealing twice does not append another block
    assert ledger.height() == sealed["ledger_block"] + 1       # the block is the head: no second block was appended


def test_sealing_with_no_session_is_an_error(tmp_path):
    with pytest.raises(LookupError):
        make(tmp_path, lambda p, r: FakePort([])).seal_last_session(Ledger(tmp_path / "l.db", tmp_path / "k.pem"))


def test_an_empty_session_leaves_no_evidence_file(tmp_path):
    b = make(tmp_path / "live", lambda p, r: FakePort([]))
    b.connect("COM_FAKE", 9600)
    time.sleep(0.2)
    b.disconnect()
    assert list((tmp_path / "live").glob("*.csv")) == []


def test_listing_ports_never_raises():
    r = list_ports()
    assert "ports" in r and isinstance(r["ports"], list)


def test_concurrent_status_reads_are_safe(tmp_path):
    b = make(tmp_path, lambda p, r: FakePort(GOOD * 20), warmup_s=0)
    b.connect("COM_FAKE", 9600)
    errs = []

    def poll():
        for _ in range(100):
            try:
                b.status()
                b.readings()
            except Exception as exc:  # noqa: BLE001
                errs.append(exc)
    ts = [threading.Thread(target=poll) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    b.disconnect()
    assert not errs
