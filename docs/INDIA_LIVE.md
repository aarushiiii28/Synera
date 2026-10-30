# India Live Intelligence

The home page of SYNERA: an interactive map of India. Click a city and SYNERA fetches its live readings, validates them, runs them through the existing engine, and returns ranked actions with the evidence behind each one.

```
LIVE DATA APIs  ->  NORMALISE  ->  VALIDATE  ->  SYNERA ENGINE  ->  EXPLANATION  ->  RANKED ACTIONS
 Open-Meteo, CAMS    units, kinds    physical        scenario model     drivers,         urgency, window,
 (+ CPCB, OpenAQ,    and sources     limits, 16/24   + Track D          interactions,    confidence, who,
  NASA FIRMS)                        hour rule       findings           model skill      evidence
```

Code: `src/synera_core/india/` (providers, normalize, guidelines, climatology, engine, recommend, service), `backend/app/api/v1/india.py`, `frontend/src/app/pages/IndiaLive.tsx`, `frontend/src/components/india/`. Tests: `tests/test_india.py`, `backend/tests/test_india_api.py`, `frontend/e2e/india.cjs`.

## Data sources

| Source | What it gives | Key | Status in this build |
|---|---|---|---|
| Open-Meteo forecast API | temperature, humidity, wind, rain, pressure, 3 days of model analysis and a forecast | none | **integrated and tested live** |
| Open-Meteo air-quality API (CAMS model) | PM2.5, PM10, NO₂, SO₂, O₃, CO, UV, a forecast | none | **integrated and tested live** |
| Open-Meteo archive | 2023 to 2025 history, to learn each city's normal for the season | none | **integrated and tested live** |
| CPCB real-time station averages (data.gov.in) | station PM2.5 / PM10 24-hour averages | `DATA_GOV_IN_API_KEY` | code and parser tested against a mocked reply; **not exercised against the live service** (no key was available) |
| OpenAQ v3 | station PM2.5 / PM10 | `OPENAQ_API_KEY` | same: mocked reply only |
| NASA FIRMS | satellite fire detections (VIIRS) near the city | `FIRMS_MAP_KEY` | same: mocked reply only; the CSV request is not exercised |
| IMD | heat-wave and rainfall *criteria* | none | IMD has no open, keyless data API, so its published criteria are applied to the model values |

Without a key a provider reports `NOT_CONFIGURED` on the Sources tab. Nothing fills the gap.

Free keys: OpenAQ (https://explore.openaq.org/register), data.gov.in (https://data.gov.in, "My account"), FIRMS (https://firms.modaps.eosdis.nasa.gov/api/map_key). Put them in the environment of the API process:

```
OPENAQ_API_KEY=...        DATA_GOV_IN_API_KEY=...        FIRMS_MAP_KEY=...        SYNERA_OFFLINE=0
```

A CPCB station average replaces the modelled PM for the AQI. OpenAQ readings are shown beside the model but are instantaneous, so they do not replace the 24-hour AQI.

## What each number is

Every metric carries a kind: **Station** (a monitor), **Model** (a weather or air-quality model's estimate of the present: Open-Meteo, CAMS), **Forecast**, **Derived** (computed by SYNERA with a published formula). The model's air quality can differ from the nearest monitor, which is why the interface says "modelled" next to the AQI.

* **AQI**: India's National AQI (CPCB 2014 breakpoints) from the **24-hour mean** of PM2.5 and PM10, requiring at least 16 of the last 24 hours. It is PM-based: the official figure also needs NO₂, SO₂, O₃, CO, NH₃ and lead, which are not available here. The interface says so.
* **Heat**: IMD heat-wave criteria (Tmax and departure from the city's own normal, by terrain; absolute 45 °C in the plains) and the NWS heat-index categories. "Heat stress today" is the larger of the heat index now and the forecast peak apparent temperature, so an evening reading does not hide the day's worst.
* **Rain**: IMD 24-hour categories. **UV**: WHO scale.
* **Composite environmental risk** (map layer): the worst single hazard of air quality, heat and rain on a common 0 to 1 scale, with the driver named. No weights.
* **Map colour between cities** is interpolated (inverse-distance) for readability and fades with distance from the nearest city. It is not a measurement.

Values outside physical limits are discarded and listed on the city's Conditions tab; missing values are shown as missing, and recommendations that depend on them are marked lower confidence or left out.

## How the existing engine is used

1. **Scenario model** (`synera_core.prediction.scenario`, the model behind the Scenario Lab): learned from real US weekly deaths, EPA air pollution and ERA5 weather (46 states, 2014 to 2019). It works in anomalies, so an Indian city is expressed against *its own* normal for this week of the year (`climatology.py`: the same calendar window of 2023 to 2025, the trailing seven-day mean of each stressor, in units of the usual variation). The output is the model's average association between the week's conditions and weekly deaths, with its 90 % range, an exact split by stressor, and the learned interaction terms with their bootstrap ranges.
   *What it is not*: it was learned in the US and is applied here in standardised units, so it is **indicative and not validated for India**; it is an average for a population, never a statement about a person. Its out-of-sample skill (R² about 0.007 on states it never saw; calibration slope 0.91) and the count of interactions that stand out from chance (7 of 45 pairs, against 4.5 expected by chance) are returned with every answer and shown on the Evidence tab. An engine-based recommendation is only issued when an interaction's range excludes zero, adds risk, and both stressors are at least one usual deviation above normal.
   Inputs the model has but India's live data cannot supply in the same definition (UV, the drought index) stay at normal, and the answer says so.
2. **Track D findings** (real Grid-India electricity demand × ERA5, replicated on later data; two are VERIFIED): the stored heat × humidity response surfaces are evaluated at today's conditions for the 16 states in those panels, in the panel's physical units, and only where the state has at least 30 days of history near today's heat–humidity pair (the fitted surface is erratic where there is no data). This is about **grid stress**, not health, and is advice to utilities and authorities.

The discovery stage's LightGBM and SHAP analysis is **not** run on live readings. The explanation uses the scenario model's exact term-by-term decomposition (a product term is split equally between its two stressors) and says that this is not a SHAP run. The engine does not infer cause anywhere.

## Recommendations

Rule-based and auditable (`recommend.py`). Each one states **action, reason (what is happening and why), affected group, urgency, time window, confidence and the data and thresholds** behind it, and whether it rests on an *official threshold* (CPCB, IMD, WHO, NWS) or on the *SYNERA engine*. They are advisories for public health and operations, not medical advice.

* Urgency: Informational, Advisory, High priority, Critical (from the official category reached).
* Confidence is **data completeness and provenance, not a probability**: it falls with missing inputs, with model-only (non-station) values, with a stale cached copy, and is capped at 0.45 for anything resting on the US-trained model.
* Timing advice uses the model forecast: for example the cleanest and dirtiest three-hour windows of the next 24 hours.

## Failure handling

All provider calls retry on network errors and 5xx, honour `Retry-After` on 429, and are cached (15 minutes live, 30 days for the climatology). If a provider fails, the last good copy is shown and marked **stale**; if there is none, the page says so and shows nothing in its place. `SYNERA_OFFLINE=1` serves cached copies only.

## Known limits

* The map shows 52 cities; adding one is one line in `src/synera_core/india/cities.py`. "Any Indian city" is not searchable, only these.
* **State boundaries** come from the open `udit-001/india-maps-data` dataset, simplified to 50 KB. Before any formal use, replace `frontend/public/data/india_states.geojson` with the Survey of India's official outline: Indian law requires official depictions, especially of Jammu and Kashmir and Ladakh.
* Modelled air quality is coarse (tens of kilometres): urban hotspots and roadside values will be higher than a city cell.
* There is no time scrubber on the map itself; the city timeline shows the past three days and the next three.
* Flooding, fire spread and health outcomes are not modelled.
* The recorded Vercel demo can only show a snapshot (see below); live data needs the API.

## Recorded demo

The server-less (Vercel) build answers from `frontend/public/snapshot/`, so the map shows a dated recording of the real providers, labelled **RECORDED SNAPSHOT**, with every city clickable. Refresh just the India part before a deploy (needs internet, takes a few minutes the first time):

```
python scripts/build_snapshot.py --india-only
```

The full `python scripts/build_snapshot.py` also refreshes it (after warming the India cache online). Without a recording the static site cannot show the map's data; it says so rather than drawing guesses.
