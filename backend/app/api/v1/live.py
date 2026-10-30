"""Live Stress Lab: a physical Arduino (DHT11 + MQ gas sensor) read over a COM port, streamed to the web app.

Provenance is explicit on every reading: ``REAL_SENSOR`` for the device, ``SIMULATED_TEST`` for the labelled test feed. The browser never invents readings
and neither does this module: when the device is absent the endpoints say so.
"""

from __future__ import annotations

import asyncio
import json

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from synera_core.benchmark.generator import load_env_panel
from synera_core.iot.analysis import analyse, load_session
from synera_core.iot.bridge import BAUDS, SerialBridge, list_ports
from synera_core.iot.readings import HEADER, SPEC
from synera_core.pipeline.registry import get_spec, summarize
from synera_core.provenance.ledger import Ledger

from backend.app.core.deps import get_bridge, get_ledger

router = APIRouter(prefix="/live", tags=["Live Stress Lab"])


class ConnectRequest(BaseModel):
    port: str = Field(min_length=2, max_length=64)
    baud: int = 9600


@router.get("/ports", summary="Serial ports the computer can see (a detected port is not proof that a device is working)")
def ports():
    return {**list_ports(), "bauds": list(BAUDS)}


@router.get("/spec", summary="What the firmware sends and what each sensor can be trusted for")
def spec():
    return {"format": HEADER, "baud_default": 9600, "interval_s": 2, "sensors": SPEC,
            "wiring": {"dht11": "VCC 5V, GND GND, OUT D2", "gas": "VCC 5V, GND GND, AO A0 (check the pin labels printed on the module: the order differs between modules)"},
            "notes": ["The gas value is the raw 10-bit ADC reading of an MQ-series sensor. It is not ppm, not AQI and not PM2.5.",
                      "The DHT11 reports whole degrees and whole percent; its accuracy is about ±2 °C and ±5 % RH.",
                      "MQ sensors need a long pre-heat: the first minutes of values are flagged WARMING_UP."]}


@router.get("/status", summary="Connection state, packet counters and the last error")
def status(bridge: SerialBridge = Depends(get_bridge)):
    return bridge.status()


@router.post("/connect", summary="Open a serial port and start reading the device")
def connect(req: ConnectRequest, bridge: SerialBridge = Depends(get_bridge)):
    try:
        return bridge.connect(req.port, req.baud)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/disconnect", summary="Close the serial port")
def disconnect(bridge: SerialBridge = Depends(get_bridge)):
    return bridge.disconnect()


@router.get("/readings", summary="Recent readings (bounded history)")
def readings(after: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=2000), bridge: SerialBridge = Depends(get_bridge)):
    return {"status": bridge.status(), "items": bridge.readings(after, limit), "latest_seq": bridge.latest_seq()}


@router.get("/stream", summary="Server-Sent Events: every new reading as it arrives, plus status changes")
async def stream(request: Request, after: int = Query(0, ge=0), bridge: SerialBridge = Depends(get_bridge)):
    async def gen():
        last, last_status, beat = after, "", 0
        while True:
            if await request.is_disconnected():
                break
            for r in bridge.readings(last, 200):
                last = r["seq"]
                yield f"id: {last}\nevent: reading\ndata: {json.dumps(r)}\n\n"
            st = bridge.status()
            key = f"{st['state']}|{st['receiving']}|{st['packets_rejected']}|{st['last_error']}"
            if key != last_status or beat >= 10:
                last_status, beat = key, 0
                yield f"event: status\ndata: {json.dumps(st)}\n\n"
            beat += 1
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class TestRequest(BaseModel):
    seed: int = 7


@router.post("/test-mode/start", summary="Start the LABELLED simulated feed (only when no hardware is connected)")
def test_start(req: TestRequest | None = None, bridge: SerialBridge = Depends(get_bridge)):
    try:
        return bridge.start_test(seed=(req.seed if req else 7))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@router.post("/test-mode/stop", summary="Stop the simulated feed")
def test_stop(bridge: SerialBridge = Depends(get_bridge)):
    return bridge.disconnect()


@router.post("/seal", summary="Fingerprint the last hardware session file and record it in the signed ledger")
def seal(bridge: SerialBridge = Depends(get_bridge), ledger: Ledger = Depends(get_ledger)):
    try:
        return bridge.seal_last_session(ledger)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.post("/analyze", summary="Run the interaction engine on the hardware session so far: does the gas reading depend on temperature and humidity together?")
def analyze(quick: bool = True, bridge: SerialBridge = Depends(get_bridge)):
    path = bridge.session_file()
    if path is None or not path.exists():
        raise HTTPException(404, "There is no hardware session to analyse. Connect the device and let it collect readings first.")
    if bridge.status()["test_mode"]:
        raise HTTPException(409, "The test generator is running; only readings from the real device are analysed.")
    return analyse(load_session(path), quick=quick)


@router.get("/history", summary="Where a reading sits among the real outdoor daily observations already in SYNERA (not like-for-like: see the caveats)")
def history(city: str = "Ludhiana", temperature: float | None = None, humidity: float | None = None):
    spec_ = get_spec("env_panel")
    if not spec_.abs_path.exists():
        raise HTTPException(404, "the historical environmental panel is not available on this machine")
    panel = load_env_panel()
    cities = sorted(panel["city"].unique().tolist())
    if city not in cities:
        raise HTTPException(404, f"no data for '{city}'; choose from {cities}")
    g = panel[panel["city"] == city]
    s = summarize(spec_)

    def dist(col: str, value: float | None, unit: str):
        v = g[col].dropna().to_numpy(float)
        q = {str(k): float(np.percentile(v, k)) for k in (5, 25, 50, 75, 95)}
        pct = None if value is None or not len(v) else float(100.0 * np.mean(v <= value))
        return {"variable": col, "unit": unit, "n_days": int(len(v)), "min": float(v.min()), "max": float(v.max()), "quantiles": q, "percentile_of_reading": pct,
                "reading": value}

    return {
        "dataset": {"id": "env_panel", "name": spec_.name, "provenance": "REAL", "source": "Open-Meteo historical archive (ERA5 reanalysis), CC BY 4.0",
                    "date_start": s.get("date_start"), "date_end": s.get("date_end"), "sha256": s.get("sha256"), "city": city, "cities": cities},
        "temperature": dist("tmean", temperature, "°C"), "humidity": dist("rh", humidity, "%"),
        "caveats": ["These are OUTDOOR DAILY MEANS for the city. A reading from a sensor in a room is an instantaneous, often indoor value: it is not like-for-like.",
                    "Gas readings have no historical counterpart in this dataset and are not compared.",
                    "The panel covers Aug 2022 to Dec 2023 only, so seasons outside that window are missing."],
    }
