"""Scenario lab: the model learned from real US mortality, weather and air-pollution data.

The model file is a short list of coefficients, so the web app downloads it once and evaluates it in the browser. The
server-side ``/predict`` endpoint runs the identical arithmetic (synera_core.prediction.scenario.predict) for API users and tests.
"""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from synera_core.prediction.scenario import OUTCOMES, predict
from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.ledger import Ledger

from backend.app.core.config import RESULTS_DIR
from backend.app.core.deps import get_ledger

router = APIRouter(prefix="/scenario", tags=["Scenario"])
OutcomeId = Literal["all", "heart", "stroke"]
_cache: dict[tuple[str, float], dict] = {}


def _model(outcome: str) -> dict:
    p = RESULTS_DIR / f"scenario_model_{outcome}.json"
    if not p.exists():
        raise HTTPException(404, f"scenario model '{outcome}' not built yet: run  python scripts/build_scenario_model.py")
    key = (outcome, p.stat().st_mtime)
    if key not in _cache:
        _cache.clear()
        _cache[key] = json.loads(p.read_text(encoding="utf-8"))
    return _cache[key]


@router.get("/outcomes", summary="Outcomes a scenario can be asked about, with how well each model checks out of sample")
def outcomes():
    out = []
    for oid, spec in OUTCOMES.items():
        p = RESULTS_DIR / f"scenario_model_{oid}.json"
        if not p.exists():
            out.append({"id": oid, "label": spec["label"], "available": False})
            continue
        m = _model(oid)
        v = m["validation"]
        out.append({"id": oid, "label": spec["label"], "available": True, "dataset_id": spec["dataset_id"], "rows": m["training"]["rows"],
                    "states": m["training"]["states"], "calibration_slope": v["calibration_slope"], "calibration_slope_ci": v["calibration_slope_ci"],
                    "r2_leave_states_out": v["leave_states_out"]["with_interactions"]})
    return out


@router.get("/model", summary="The full model (coefficients, bootstrap replicates, state climatologies, validation)")
def model(outcome: OutcomeId = "all", ledger: Ledger = Depends(get_ledger)):
    m = _model(outcome)
    # the model file is fingerprinted and registered in the ledger like a dataset; report where, so anyone can check it
    sha = sha256_file(RESULTS_DIR / f"scenario_model_{outcome}.json")
    found = ledger.find_by_artifact(sha)
    return {**m, "registered": {"sha256": sha, "ledger_block": found[0][0].index if found else None}}


class PredictRequest(BaseModel):
    outcome: OutcomeId = "all"
    state: str
    week: int = Field(ge=1, le=52, description="week of the year, 1-52")
    levels: dict[str, float] | None = Field(None, description="absolute stressor levels in physical units; omitted ones stay normal")
    anomalies: dict[str, float] | None = Field(None, description="stressor anomalies in the state's usual deviations (alternative to levels)")


@router.post("/predict", summary="Effect of a combination of stressors on weekly deaths versus a typical week, with a 90% interval")
def predict_scenario(req: PredictRequest):
    m = _model(req.outcome)
    if req.state not in m["locations"]:
        raise HTTPException(404, f"no data for state '{req.state}' in this model")
    unknown = [k for k in {**(req.levels or {}), **(req.anomalies or {})} if k not in m["stressors"]]
    if unknown:
        raise HTTPException(400, f"unknown stressor(s) {unknown}; choose from {m['stressors']}")
    r = predict(m, req.state, req.week - 1, req.levels, req.anomalies)
    return {**r, "outcome": m["outcome"], "dataset": m["dataset"], "state": req.state, "week": req.week,
            "note": "Average association in past state-weeks (2014-2019), not a forecast for any individual and not proof of cause."}
