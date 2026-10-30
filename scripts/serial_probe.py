"""Check the Arduino from a terminal, without the web app.

    python scripts/serial_probe.py                  # lists the serial ports
    python scripts/serial_probe.py COM14            # reads 10 seconds at 9600 baud and prints every parsed reading
    python scripts/serial_probe.py COM14 --baud 9600 --seconds 20

It uses the same parser and the same validation as the Live Stress Lab, so what it prints is exactly what the page would show. Close the Arduino
IDE Serial Monitor first: a serial port can be open in only one program at a time.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from synera_core.iot.bridge import list_ports  # noqa: E402
from synera_core.iot.readings import ParseError, is_noise, parse_line  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--seconds", type=float, default=10.0)
    a = ap.parse_args()
    found = list_ports()
    if not found["available"]:
        print(found["note"])
        return 2
    if not a.port:
        print("Serial ports:" if found["ports"] else "No serial ports found.")
        for p in found["ports"]:
            print(f"  {p['device']:8s} {p['description']}")
        return 0
    import serial
    try:
        s = serial.Serial(a.port, a.baud, timeout=1.0)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not open {a.port}: {exc}\nIf it says access denied, close the Arduino IDE Serial Monitor (or any program using the port).")
        return 1
    ok = bad = 0
    end = time.time() + a.seconds
    print(f"Reading {a.port} at {a.baud} baud for {a.seconds:.0f} s ...")
    try:
        while time.time() < end:
            raw = s.readline().decode("ascii", errors="replace").strip()
            if is_noise(raw):
                if raw.startswith("#"):
                    print("  ", raw)
                continue
            try:
                t, parsed = parse_line(raw)
                ok += 1
                print(f"  t={t:>7} ms  " + "  ".join(f"{k}={'missing' if v is None else f'{v:g}'} [{q}]" for k, v, q in parsed))
            except ParseError as exc:
                bad += 1
                print(f"  rejected: {exc.reason}   ({raw[:40]!r})")
    finally:
        s.close()
    print(f"{ok} valid readings, {bad} rejected lines.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
