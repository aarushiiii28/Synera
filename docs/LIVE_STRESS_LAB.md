# Live Stress Lab

A physical Arduino Uno (DHT11 temperature and humidity sensor, MQ-series gas sensor) read over USB, streamed into SYNERA, with scenario building, an exploratory interaction view, a comparison with real historical data and a provenance record for every value. Route: `/live-stress-lab`.

## Architecture

```
Arduino Uno --USB/COM--> synera_core.iot.bridge (pyserial thread, inside the API process)
                              |  parse + validate every line (synera_core.iot.readings)
                              |  bounded history (2000 readings) + session CSV  data/live/session_*.csv  (git-ignored)
                              v
                    FastAPI  /api/v1/live/*   (REST + Server-Sent Events)
                              v
              React page  /live-stress-lab    (EventSource, bounded history in the browser)
```

The "serial bridge" is the Python module `src/synera_core/iot/bridge.py`. It runs inside the API process because the API runs on the same computer as the Arduino; there is no second service to start. `scripts/serial_probe.py` runs the same parser from a terminal.

## What is real, simulated, historical, derived

| Where | Class | Meaning |
|---|---|---|
| Temperature, humidity (DHT11), gas raw (MQ, A0) | REAL SENSOR | measured by the connected device; stored unchanged, no smoothing, no calibration, no gap filling |
| PM2.5, PM10, CO₂ in the scenario builder | SIMULATED | numbers you type; no such sensor is attached |
| The test feed (button in the connection panel) | SIMULATED | labelled `SIMULATED_TEST`, blocked while hardware is connected, never written as evidence |
| Outdoor daily temperature and humidity (section 07) | HISTORICAL | SYNERA `env_panel`, Open-Meteo / ERA5, 8 cities, Aug 2022 to Dec 2023 |
| Heat index, dew point, the 2 x 2 contrast | DERIVED | formulas applied to temperature and humidity (heat index equals `calculate_heat_index` used for the historical panels; a test checks this to 6 decimals) |

## Honesty rules the code enforces

* **CONNECTED means valid packets are arriving.** A port that opens but stays silent is `CONNECTING`, then `ERROR` after 12 s with the reason.
* **No data, no chart.** When the device is absent the page is empty and says why; nothing is drawn from invented values. Unplugging gives `RECONNECTING`, never fabricated readings.
* **Missing is missing.** If the DHT11 does not answer, the firmware sends empty fields and the page shows "missing", not zero.
* **Gas is a raw ADC value** (0 to 1023), not ppm, not AQI, not PM2.5; the first 120 s after connecting are flagged `WARMING_UP`.
* **The interaction explorer is exploratory.** It computes a deviation from additivity of the *heat index* (a formula). It produces no p-values, q-values or biological claims, and it says that environmental readings alone cannot establish biological effects. It is separate from the NASA GeneLab analysis.

## Wiring (the software assumes this; the pin constants are at the top of the firmware)

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

Close the Arduino IDE Serial Monitor first: a COM port can be open in one program only. Check the device from a terminal with `python scripts/serial_probe.py COM14`.

`SYNERA_GAS_WARMUP_S` (default 120) sets how long the gas value is flagged as warming up.

## API

`GET /live/ports`, `GET /live/spec`, `GET /live/status`, `POST /live/connect {port, baud}`, `POST /live/disconnect`, `GET /live/readings?after=&limit=`, `GET /live/stream` (SSE: `reading` and `status` events), `POST /live/test-mode/start|stop`, `POST /live/seal` (fingerprints the last hardware session file and records it as a `DATASET_REGISTERED` block with provenance `REAL_SENSOR`), `GET /live/history?city=&temperature=&humidity=`.

Every reading carries: device id, sensor, value, unit, device time, receive time, source (`REAL_SENSOR` or `SIMULATED_TEST`) and quality (`OK`, `MISSING`, `OUT_OF_SENSOR_RANGE`, `WARMING_UP`).

## Tests

* `tests/test_iot.py` (parsing, invalid and missing values, the bridge with a fake port: disconnect, reconnect, bounded history, silent port, test feed isolation, sealing) and `backend/tests/test_live_api.py` (the API with a fake port). The fake port exercises the software only; it proves nothing about the hardware.
* `frontend/src/tests/live.test.ts` and `live.components.test.tsx` (heat index equals the Python one, statistics, bounded history, scenario and interaction arithmetic, empty states, provenance labels).
* `frontend/e2e/live.cjs`: page, empty states, the labelled simulated feed, scenario builder, interaction explorer. With `LIVE_HARDWARE=1` it also connects the real Arduino; only that run verifies the physical integration.
* `frontend/e2e/static.cjs` checks that the recorded demo makes no hardware claim.

## Limits

DHT11: whole degrees and whole percent, ±2 °C and ±5 % RH. The gas sensor is uncalibrated and responds to several gases. A room reading is not an outdoor daily mean, so the historical comparison is a context, not a like-for-like test. A few hours of readings cannot discover statistical interactions: that needs a measured outcome and many observations (see the Discovery Lab).
