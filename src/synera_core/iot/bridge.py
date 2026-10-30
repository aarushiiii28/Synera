"""The serial bridge: Arduino Uno -> USB / COM port -> this module -> SYNERA.

It owns exactly one serial port at a time (the Arduino Serial Monitor cannot share it), reads newline-delimited CSV packets, validates every
line, keeps a bounded in-memory history for the live page and writes the real readings of a session to a CSV file that can later be sealed
into the evidence ledger.

Honesty rules enforced here:

* ``CONNECTED`` means valid packets are actually arriving. A port that opened but stays silent is ``CONNECTING`` and, after
  ``no_data_timeout_s``, ``ERROR`` with a reason. A detected COM port alone proves nothing.
* When the device goes away the state becomes ``RECONNECTING``. No reading is ever generated to fill the gap.
* The explicitly labelled test generator can only run while no hardware is connected; its readings carry ``source = SIMULATED_TEST``, are never
  written to a session file and never sealed.
"""
from __future__ import annotations

import csv
import math
import random
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from synera_core.iot.readings import (
    SOURCE_REAL, SOURCE_TEST, ParseError, Reading, build_reading, is_noise, parse_line,
)
from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.ledger import Ledger

DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, ERROR, TEST_MODE = "DISCONNECTED", "CONNECTING", "CONNECTED", "RECONNECTING", "ERROR", "TEST_MODE"
BAUDS = (9600, 19200, 38400, 57600, 115200)
SESSION_COLUMNS = ["seq", "received_utc", "device_id", "time_ms", "temperature_C", "humidity_pct", "gas_raw", "temperature_quality", "humidity_quality", "gas_quality", "source"]


def list_ports() -> dict[str, Any]:
    """Serial ports the computer can see. Detecting a port says nothing about whether a working device is behind it."""
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        return {"available": False, "ports": [], "note": "pyserial is not installed in the API's Python environment (pip install pyserial)."}
    ports = [{"device": p.device, "description": p.description or "", "manufacturer": p.manufacturer or "", "hwid": p.hwid or ""} for p in lp.comports()]
    ports.sort(key=lambda p: p["device"])
    return {"available": True, "ports": ports, "note": None}


def default_opener(port: str, baud: int):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is not installed in the API's Python environment (pip install pyserial)") from exc
    return serial.Serial(port, baud, timeout=1.0)


class SessionRecorder:
    """Appends the REAL readings of one connection to a CSV file (flushed per line, so a crash loses nothing)."""

    def __init__(self, directory: Path, port: str, now: datetime | None = None):
        directory.mkdir(parents=True, exist_ok=True)
        stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
        safe = "".join(c for c in port if c.isalnum())
        self.path = directory / f"session_{stamp}_{safe}.csv"
        self.rows = 0
        self._fh = self.path.open("w", newline="", encoding="utf-8")
        self._w = csv.writer(self._fh)
        self._w.writerow(SESSION_COLUMNS)
        self._fh.flush()

    def write(self, r: Reading) -> None:
        m = {x.sensor: x for x in r.measurements}
        self._w.writerow([r.seq, r.received_utc, r.device_id, r.time_ms, "" if m["temperature"].value is None else m["temperature"].value,
                          "" if m["humidity"].value is None else m["humidity"].value, "" if m["gas"].value is None else int(m["gas"].value),
                          m["temperature"].quality, m["humidity"].quality, m["gas"].quality, r.source])
        self._fh.flush()
        self.rows += 1

    def close(self) -> None:
        try:
            self._fh.close()
        except OSError:
            pass


class SerialBridge:
    def __init__(self, data_dir: Path, opener: Callable[[str, int], Any] = default_opener, warmup_s: float = 120.0, buffer_size: int = 2000,
                 no_data_timeout_s: float = 12.0, retry_s: float = 2.0, clock: Callable[[], float] = time.time):
        self.data_dir = Path(data_dir)
        self._opener, self.warmup_s, self.no_data_timeout_s, self.retry_s, self._clock = opener, warmup_s, no_data_timeout_s, retry_s, clock
        self._buf: deque[Reading] = deque(maxlen=buffer_size)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._recorder: SessionRecorder | None = None
        self._last_session: dict[str, Any] | None = None
        self._seq = 0
        self._reset_status()

    # ---------------------------------------------------------------- status
    def _reset_status(self) -> None:
        self._s: dict[str, Any] = {"state": DISCONNECTED, "port": None, "baud": None, "device_id": None, "source": None, "message": "Not connected.",
                                   "packets_ok": 0, "packets_rejected": 0, "last_error": None, "last_packet_utc": None, "connected_since_utc": None,
                                   "opened_at": None, "last_packet_at": None}

    def status(self) -> dict[str, Any]:
        with self._lock:
            s = dict(self._s)
        now = self._clock()
        s["receiving"] = bool(s["last_packet_at"] and now - s["last_packet_at"] < max(6.0, self.no_data_timeout_s / 2))
        s["seconds_since_packet"] = None if not s["last_packet_at"] else round(now - s["last_packet_at"], 1)
        s["buffered"] = len(self._buf)
        s["session"] = None if not self._recorder else {"file": self._recorder.path.name, "rows": self._recorder.rows}
        s.pop("opened_at"), s.pop("last_packet_at")
        s["last_session"] = self._last_session
        s["test_mode"] = s["state"] == TEST_MODE
        return s

    def _set(self, **kw: Any) -> None:
        with self._lock:
            self._s.update(kw)

    # ---------------------------------------------------------------- readings
    def latest_seq(self) -> int:
        return self._seq

    def readings(self, after: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            out = [r for r in self._buf if r.seq > after]
        return [r.to_dict() for r in out[-limit:]] if after == 0 else [r.to_dict() for r in out[:limit]]

    def _push(self, time_ms: int, parsed: list, source: str, device_id: str, warming: bool) -> Reading:
        with self._lock:
            self._seq += 1
            r = build_reading(self._seq, device_id, time_ms, parsed, source, warming_up=warming)
            self._buf.append(r)
            self._s["packets_ok"] += 1
            self._s["last_packet_utc"] = r.received_utc
            self._s["last_packet_at"] = self._clock()
        return r

    # ---------------------------------------------------------------- hardware
    def connect(self, port: str, baud: int = 9600, wait_s: float = 4.0) -> dict[str, Any]:
        if baud not in BAUDS:
            raise ValueError(f"baud rate {baud} is not one of {BAUDS}")
        if not port or not isinstance(port, str):
            raise ValueError("a serial port name is required")
        self.disconnect()
        with self._lock:
            self._buf.clear()
            self._reset_status()
            self._s.update(state=CONNECTING, port=port, baud=baud, source=SOURCE_REAL, device_id=f"uno@{port}", message=f"Opening {port} at {baud} baud ...")
        self._stop = threading.Event()
        self._recorder = SessionRecorder(self.data_dir, port)
        self._thread = threading.Thread(target=self._run, args=(port, baud, self._stop), name="synera-serial-bridge", daemon=True)
        self._thread.start()
        t_end = self._clock() + wait_s
        while self._clock() < t_end and self.status()["state"] == CONNECTING and self._s["opened_at"] is None and self._s["last_error"] is None:
            time.sleep(0.05)
        return self.status()

    def disconnect(self) -> dict[str, Any]:
        self._stop.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3.0)
        self._thread = None
        if self._recorder:
            rec, self._recorder = self._recorder, None
            rec.close()
            if rec.rows:
                self._last_session = {"file": rec.path.name, "rows": rec.rows, "path": str(rec.path), "sealed": False}
            else:
                try:
                    rec.path.unlink()          # nothing was received: no empty evidence file
                except OSError:
                    pass
        with self._lock:
            keep = self._s["packets_ok"], self._s["packets_rejected"]
            self._buf.clear()          # a disconnected lab shows an empty state, not the previous session's readings (the session file stays as evidence)
            self._reset_status()
            self._s["message"] = "Disconnected." if not keep[0] else f"Disconnected after {keep[0]} valid packets."
        return self.status()

    def _run(self, port: str, baud: int, stop: threading.Event) -> None:
        ser = None
        had_data = False
        while not stop.is_set():
            try:
                ser = self._opener(port, baud)
            except Exception as exc:  # noqa: BLE001 - any open failure is reported to the user as it is
                msg = f"Could not open {port}: {exc}"
                if "denied" in str(exc).lower() or "busy" in str(exc).lower() or "permission" in str(exc).lower():
                    msg += " (another program, such as the Arduino IDE Serial Monitor, probably holds the port: close it and connect again)"
                self._set(state=RECONNECTING if had_data else ERROR, last_error=msg, message=msg)
                if stop.wait(self.retry_s):
                    return
                continue
            opened = self._clock()
            self._set(state=CONNECTING if not had_data else RECONNECTING, opened_at=opened, last_error=None,
                      message=f"{port} is open at {baud} baud. Waiting for the first valid packet ...")
            device_id = f"uno@{port}"
            connected_at = None
            try:
                while not stop.is_set():
                    raw = ser.readline()
                    if not raw:
                        if self._s["state"] != CONNECTED and self._clock() - opened > self.no_data_timeout_s:
                            self._set(state=ERROR, last_error="The port opened but no valid data arrived. Check the baud rate, the firmware and the wiring.",
                                      message="Port open, but no valid data.")
                        continue
                    line = raw.decode("ascii", errors="replace").strip() if isinstance(raw, (bytes, bytearray)) else str(raw).strip()
                    if line.startswith("# device="):
                        device_id = line.split("=", 1)[1].strip() or device_id
                        self._set(device_id=device_id)
                    if is_noise(line):
                        continue
                    try:
                        time_ms, parsed = parse_line(line)
                    except ParseError as exc:
                        with self._lock:
                            self._s["packets_rejected"] += 1
                            self._s["last_error"] = f"rejected a line: {exc.reason}"
                        continue
                    if connected_at is None:
                        connected_at = self._clock()
                        self._set(state=CONNECTED, connected_since_utc=datetime.now(UTC).isoformat(timespec="seconds"),
                                  message="Valid packets are arriving from the device.", last_error=None)
                        had_data = True
                    r = self._push(time_ms, parsed, SOURCE_REAL, device_id, warming=self._clock() - connected_at < self.warmup_s)
                    if self._recorder:
                        self._recorder.write(r)
            except Exception as exc:  # noqa: BLE001 - serial.SerialException on unplug, OSError on a dropped USB device
                msg = f"The device stopped responding: {exc}"
                self._set(state=RECONNECTING, last_error=msg, message=f"{msg}. Trying to reconnect ...")
            finally:
                try:
                    if ser is not None:
                        ser.close()
                except Exception:  # noqa: BLE001
                    pass
            if stop.wait(self.retry_s):
                return

    # ---------------------------------------------------------------- test generator (explicitly simulated)
    def start_test(self, rate_hz: float = 0.5, seed: int = 7) -> dict[str, Any]:
        if self._s["state"] in (CONNECTING, CONNECTED, RECONNECTING):
            raise RuntimeError("Hardware is connected. Disconnect it before starting the simulated test feed, so the two can never be mixed.")
        self.disconnect()
        with self._lock:
            self._buf.clear()
            self._reset_status()
            self._s.update(state=TEST_MODE, source=SOURCE_TEST, device_id="SIMULATED-TEST-GENERATOR", message="SIMULATED TEST DATA. Nothing here is measured by a sensor.")
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._test_loop, args=(rate_hz, seed, self._stop), name="synera-test-feed", daemon=True)
        self._thread.start()
        return self.status()

    def _test_loop(self, rate_hz: float, seed: int, stop: threading.Event) -> None:
        rng = random.Random(seed)
        t0, i = self._clock(), 0
        while not stop.is_set():
            ph = i / 30.0
            temp = round(26 + 1.5 * math.sin(ph) + rng.uniform(-0.4, 0.4))
            hum = round(55 + 6 * math.cos(ph / 1.7) + rng.uniform(-1, 1))
            gas = int(max(0, min(1023, 80 + 12 * math.sin(ph / 2) + rng.uniform(-4, 4))))
            self._push(int((self._clock() - t0) * 1000), [("temperature", float(temp), "OK"), ("humidity", float(hum), "OK"), ("gas", float(gas), "OK")],
                       SOURCE_TEST, "SIMULATED-TEST-GENERATOR", warming=False)
            i += 1
            if stop.wait(1.0 / max(rate_hz, 0.05)):
                return

    # ---------------------------------------------------------------- evidence
    def session_file(self) -> Path | None:
        """The CSV of the session being recorded, or of the last hardware session; ``None`` when there is none."""
        if self._recorder and self._recorder.rows:
            return self._recorder.path
        s = self._last_session
        return Path(s["path"]) if s else None

    def seal_last_session(self, ledger: Ledger) -> dict[str, Any]:
        """Hash the last real session file and record it in the signed ledger, so any later edit of the file is detectable."""
        if self._recorder and self._recorder.rows:        # a live session is still being written: close it first so the hash is final
            self.disconnect()
        s = self._last_session
        if not s:
            raise LookupError("There is no recorded hardware session to seal. Connect the device, collect readings, then seal.")
        if s.get("sealed"):
            return s
        path = Path(s["path"])
        digest = sha256_file(path)
        blk = ledger.append("DATASET_REGISTERED", {"path": path.name, "kind": "live_sensor_session", "provenance": "REAL_SENSOR", "rows": s["rows"],
                                                   "columns": SESSION_COLUMNS, "note": "readings from a physical Arduino Uno (DHT11 + MQ gas sensor), uncalibrated"},
                            artifact_hashes=[digest])
        s.update(sealed=True, sha256=digest, ledger_block=blk.index)
        return s
