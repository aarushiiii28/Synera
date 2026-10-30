"""Sensor packets from the Arduino: parsing and validation.

The firmware prints one newline-delimited CSV line per sample:

    time_ms,temperature_C,humidity_pct,gas_raw
    2000,26.0,57.0,67

* ``temperature_C`` and ``humidity_pct`` come from a DHT11. When the DHT11 does not answer, the firmware leaves both fields empty
  (``2000,,,67``): a missing value is reported as missing and is never replaced by a guess.
* ``gas_raw`` is the 10-bit ADC value (0 to 1023) of an MQ-series analog output. It is NOT a concentration: it is not ppm, not AQI and not PM2.5.

Lines starting with ``#`` are comments (the firmware announces itself with ``# device=...``) and the column header is recognised and skipped.
Nothing here ever invents a number: a line is either a valid packet, or it is rejected with the reason.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

SOURCE_REAL = "REAL_SENSOR"
SOURCE_TEST = "SIMULATED_TEST"

HEADER = "time_ms,temperature_C,humidity_pct,gas_raw"

# What each sensor can be trusted for (DHT11 data sheet) and what is physically possible at all.
SPEC = {
    "temperature": {"unit": "°C", "sensor": "DHT11", "spec_range": (0.0, 50.0), "physical_range": (-40.0, 85.0), "resolution": 1.0, "accuracy": "±2 °C"},
    "humidity": {"unit": "%", "sensor": "DHT11", "spec_range": (20.0, 90.0), "physical_range": (0.0, 100.0), "resolution": 1.0, "accuracy": "±5 % RH"},
    "gas": {"unit": "ADC counts (0-1023)", "sensor": "MQ-series analog output", "spec_range": (0.0, 1023.0), "physical_range": (0.0, 1023.0), "resolution": 1.0,
            "accuracy": "uncalibrated: a raw voltage reading, not a concentration"},
}

OK, MISSING, OUT_OF_SPEC, WARMING_UP = "OK", "MISSING", "OUT_OF_SENSOR_RANGE", "WARMING_UP"


class ParseError(ValueError):
    """The line is not a usable packet; ``reason`` says why (shown in the interface, never swallowed silently)."""

    def __init__(self, reason: str, line: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.line = line[:80]


@dataclass(frozen=True)
class Measurement:
    sensor: str                 # temperature | humidity | gas
    value: float | None
    unit: str
    quality: str                # OK | MISSING | OUT_OF_SENSOR_RANGE | WARMING_UP

    def to_dict(self) -> dict[str, Any]:
        return {"sensor": self.sensor, "value": self.value, "unit": self.unit, "quality": self.quality}


@dataclass(frozen=True)
class Reading:
    seq: int
    device_id: str
    time_ms: int                # the device's own clock (milliseconds since it started)
    received_utc: str           # when the computer received it
    source: str                 # REAL_SENSOR or SIMULATED_TEST
    measurements: tuple[Measurement, ...] = field(default_factory=tuple)

    def value(self, sensor: str) -> float | None:
        return next((m.value for m in self.measurements if m.sensor == sensor), None)

    def to_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "device_id": self.device_id, "time_ms": self.time_ms, "received_utc": self.received_utc, "source": self.source,
                "measurements": [m.to_dict() for m in self.measurements]}


def _number(text: str, name: str) -> float | None:
    t = text.strip()
    if t == "":
        return None
    try:
        v = float(t)
    except ValueError as exc:
        raise ParseError(f"{name} is not a number: {t[:20]!r}") from exc
    if math.isnan(v) or math.isinf(v):
        raise ParseError(f"{name} is not finite")
    return v


def _check(sensor: str, value: float | None) -> tuple[float | None, str]:
    spec = SPEC[sensor]
    if value is None:
        return None, MISSING
    lo, hi = spec["physical_range"]
    if not lo <= value <= hi:
        raise ParseError(f"{sensor} {value:g} is outside what is physically possible ({lo:g} to {hi:g})")
    slo, shi = spec["spec_range"]
    return value, OK if slo <= value <= shi else OUT_OF_SPEC


def is_noise(line: str) -> bool:
    """Blank lines, comments and the column header carry no measurement."""
    s = line.strip()
    return s == "" or s.startswith("#") or s.replace(" ", "").lower() == HEADER.lower()


def parse_line(line: str) -> tuple[int, list[tuple[str, float | None, str]]]:
    """Parse one CSV line into (time_ms, [(sensor, value, quality), ...]). Raises :class:`ParseError` with the reason."""
    parts = line.strip().split(",")
    if len(parts) != 4:
        raise ParseError(f"expected 4 comma-separated fields, got {len(parts)}", line)
    try:
        t = _number(parts[0], "time_ms")
        temp = _number(parts[1], "temperature_C")
        hum = _number(parts[2], "humidity_pct")
        gas = _number(parts[3], "gas_raw")
    except ParseError as exc:
        raise ParseError(exc.reason, line) from None
    if t is None or t < 0 or t != int(t):
        raise ParseError("time_ms must be a non-negative whole number", line)
    if gas is None:
        raise ParseError("gas_raw is missing", line)
    if gas != int(gas):
        raise ParseError("gas_raw must be a whole number of ADC counts", line)
    try:
        out = [("temperature", *_check("temperature", temp)), ("humidity", *_check("humidity", hum)), ("gas", *_check("gas", gas))]
    except ParseError as exc:
        raise ParseError(exc.reason, line) from None
    return int(t), out


def build_reading(seq: int, device_id: str, time_ms: int, parsed: list[tuple[str, float | None, str]], source: str = SOURCE_REAL,
                  warming_up: bool = False, now: datetime | None = None) -> Reading:
    ms = []
    for sensor, value, quality in parsed:
        if sensor == "gas" and warming_up and quality == OK:
            quality = WARMING_UP          # MQ sensors need a long pre-heat: the value is shown but flagged
        ms.append(Measurement(sensor, value, SPEC[sensor]["unit"], quality))
    return Reading(seq=seq, device_id=device_id, time_ms=time_ms, received_utc=(now or datetime.now(UTC)).isoformat(timespec="milliseconds"),
                   source=source, measurements=tuple(ms))
