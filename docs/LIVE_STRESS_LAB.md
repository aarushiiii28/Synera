# Live Stress Lab

A physical Arduino Uno (DHT11 temperature and humidity sensor, MQ gas sensor) read over USB and streamed into SYNERA at `/live-stress-lab`. There is nothing to adjust: the page shows live readings and charts, and works out what they mean automatically.

## What the page shows

1. **Connect the device**: choose the serial port and open it. The status is CONNECTED only once valid readings arrive.
2. **What this means** (computed from the live readings):
   * **Heat comfort**: the heat index from the measured temperature and humidity, in the US National Weather Service categories.
   * **Smoke alert**: the gas level against this room's own clean-air baseline (the median of its lowest fifth of readings, learned over the first 30 readings). "Smoke or gas detected" needs the last three readings to be at least 50 % above that baseline.
   * **Engine estimate**: the Scenario Lab model (learned from real CDC deaths, EPA air and ERA5 weather for 46 US states, 2014 to 2019) evaluated for the measured heat index and humidity in a chosen US state and month, giving the estimated change in weekly deaths with a 90 % range. It is an average association, not a forecast for a person, and the readings come from one room.
3. **Live readings** and **live charts** with a time window and pause.

## What the sensors can and cannot do

* The temperature and humidity come from a DHT11 (whole degrees and whole percent, about ±2 °C and ±5 % RH).
* The gas value is the raw 10-bit reading of an MQ sensor. It reacts to smoke and several other gases and is uncalibrated: it is shown as "smoke / gas level" relative to its own baseline, and it is **not** a particle concentration. The engine estimate therefore does not include an air-pollution term: SYNERA has no PM2.5 measurement, and the gas reading is never passed to the model as one. Air-pollution scenarios with an assumed PM2.5 are in the Scenario Lab, where the value is typed by the user.
* A missing DHT11 value is shown as missing, never as zero. If the device is silent or unplugged the page says so and draws nothing.

## Architecture

```
Arduino Uno --USB/COM--> synera_core.iot.bridge (pyserial thread, inside the API process)
                              |  parse + validate every line (synera_core.iot.readings)
                              |  bounded history (2000 readings) + session CSV  data/live/session_*.csv  (git-ignored)
                              v
                    FastAPI  /api/v1/live/*   (REST + Server-Sent Events)
                              v
              React page  /live-stress-lab    (EventSource, bounded history in the browser; the engine estimate runs in the browser)
```

The serial bridge is the Python module `src/synera_core/iot/bridge.py`; it runs inside the API process because the API runs on the same computer as the Arduino. A hardware session can be fingerprinted and recorded in the signed ledger ("Seal this session in the ledger"; block type `DATASET_REGISTERED`, provenance `REAL_SENSOR`). `scripts/serial_probe.py` runs the same parser from a terminal.

## Wiring (the pin constants are at the top of the firmware)

| Module | Pin |
|---|---|
| DHT11 VCC / GND / OUT | 5V / GND / **D2** |
| Gas module VCC / GND / AO | 5V / GND / **A0** (check the labels printed on your module: the order differs; DO is not used) |
| D0, D1 | keep free: they are the USB serial line |

Firmware: `firmware/synera_live_stress_lab/synera_live_stress_lab.ino` (no libraries). Upload with the Arduino IDE, or `arduino-cli compile --fqbn arduino:avr:uno firmware/synera_live_stress_lab` then `arduino-cli upload -p COM14 --fqbn arduino:avr:uno firmware/synera_live_stress_lab`. It prints `time_ms,temperature_C,humidity_pct,gas_raw` every 2 s at 9600 baud.

## Run it

```
pip install pyserial                 # or: pip install -e ".[iot]"   (already in requirements.lock)
.\dev.cmd                            # API on 8000 and web on 5173
# open http://localhost:5173/live-stress-lab , choose the port, press CONNECT
```

Close the Arduino IDE Serial Monitor first: a COM port can be open in one program only. Check the device from a terminal with `python scripts/serial_probe.py COM14`. `SYNERA_GAS_WARMUP_S` (default 120) sets how long the gas value is flagged as warming up.

## API

`GET /live/ports`, `GET /live/spec`, `GET /live/status`, `POST /live/connect {port, baud}`, `POST /live/disconnect`, `GET /live/readings?after=&limit=`, `GET /live/stream` (SSE: `reading` and `status` events), `POST /live/seal`, `GET /live/history`. The API also keeps a developer-only generator for testing the interface without hardware (`/live/test-mode/*`); the web page does not offer it.

## Tests

* `tests/test_iot.py` and `backend/tests/test_live_api.py`: parsing, invalid and missing values, the bridge with a fake port (disconnect, reconnect, bounded history, silent port, sealing), the API. The fake port exercises the software only.
* `frontend/src/tests/live.test.ts` and `live.components.test.tsx`: the heat index equals the Python one to 6 decimals, categories, statistics, bounded history, smoke baseline, empty states.
* `frontend/e2e/live.cjs`: the page and empty states; with `LIVE_HARDWARE=1` it connects the real Arduino and checks the live charts, heat comfort, smoke alert and engine estimate. Only that run verifies the physical integration.
