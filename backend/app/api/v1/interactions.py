"""Interaction matrix and network built from the latest completed run of a dataset."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.app.db.database import get_session
from backend.app.db.models import Finding, Run

router = APIRouter(tags=["Interactions"])

STRESSORS = {
    "heat_index": {"label": "Heat index", "unit": "deg C (apparent temperature)", "group": "heat",
                   "about": "How hot it feels, from temperature and humidity (Rothfusz regression)."},
    "pm25": {"label": "PM2.5", "unit": "ug/m3", "group": "air", "about": "Fine particulate matter, a main driver of air-pollution harm."},
    "pm10": {"label": "PM10", "unit": "ug/m3", "group": "air", "about": "Coarse particulate matter."},
    "o3": {"label": "Ozone", "unit": "ug/m3", "group": "air", "about": "Ground-level ozone."},
    "no2": {"label": "NO2", "unit": "ug/m3", "group": "air", "about": "Nitrogen dioxide from traffic and combustion."},
    "rh": {"label": "Relative humidity", "unit": "%", "group": "weather", "about": "Moisture in the air."},
    "drought_index": {"label": "Drought index", "unit": "z-score", "group": "drought",
                      "about": "30-day rainfall deficit against the city's climate; higher means drier."},
    "uv": {"label": "UV index", "unit": "index", "group": "weather", "about": "Ultraviolet radiation intensity."},
    "wind": {"label": "Wind", "unit": "km/h", "group": "weather", "about": "Daily maximum wind speed."},
    "precip": {"label": "Precipitation", "unit": "mm", "group": "weather", "about": "Daily rainfall."},
    # India electricity panels (Track D)
    "tmax": {"label": "Maximum temperature", "unit": "deg C", "group": "heat", "about": "Hottest 2 m air temperature of the day (state-level ERA5)."},
    "solar": {"label": "Solar radiation", "unit": "kWh/m2/day", "group": "weather", "about": "Sunlight reaching the surface, a state-level ERA5 daily mean."},
    "cloud": {"label": "Cloud cover", "unit": "fraction", "group": "weather", "about": "Share of sky covered by cloud, 0 to 1 (state-level ERA5 daily mean)."},
}


def _latest_run(session: Session, dataset_id: str) -> Run:
    run = session.exec(select(Run).where(Run.dataset_id == dataset_id, Run.status == "COMPLETED")
                       .order_by(Run.created_at.desc())).first()
    if not run or not run.pairs:
        raise HTTPException(404, f"no completed panel run for '{dataset_id}'; start one with POST /runs")
    return run


@router.get("/stressors", summary="Plain-language description of every stressor")
def stressors():
    return STRESSORS


@router.get("/interactions/matrix", summary="Every stressor pair: selected, explained away, or not significant")
def interaction_matrix(dataset_id: str = "benchmark_track_b", session: Session = Depends(get_session)):
    run = _latest_run(session, dataset_id)
    findings = {(f.stressor_a, f.stressor_b): f for f in session.exec(select(Finding).where(Finding.dataset_id == dataset_id)).all()}
    cells = []
    for p in run.pairs or []:
        f = findings.get((p["a"], p["b"]))
        cat = "selected" if p["s3_conditional"] else ("explained_away" if p["s2_bh"] else "not_significant")
        cells.append({
            "a": p["a"], "b": p["b"], "category": cat, "type": f.interaction_type if f else None, "status": f.status if f else None,
            "finding_id": f.id if f else None, "effect_size": f.effect_size if f else None,
            "q_marginal": p["q_boot"], "p_conditional": p.get("conditional_p"), "gbm_rank": p.get("gbm_rank"), "nid_rank": p.get("nid_rank"),
            "methods": f.methods if f else None, "p_naive": p["p_naive"],
        })
    names = sorted({c["a"] for c in cells} | {c["b"] for c in cells})
    return {"dataset_id": dataset_id, "run_id": run.id, "stressors": names, "cells": cells,
            "explanation": {"selected": "Survives FDR and conditional selection (not explained by another pair).",
                            "explained_away": "Significant on its own but explained by a selected pair, usually through a correlated stressor.",
                            "not_significant": "No evidence of interaction."}}


@router.get("/interactions/network", summary="Stressors as nodes, selected interactions as edges")
def interaction_network(dataset_id: str = "benchmark_track_b", session: Session = Depends(get_session)):
    run = _latest_run(session, dataset_id)
    findings = session.exec(select(Finding).where(Finding.dataset_id == dataset_id)).all()
    used = {s for f in findings for s in (f.stressor_a, f.stressor_b)}
    nodes = [{"id": s, **STRESSORS.get(s, {"label": s, "group": "other"}), "degree": sum(s in (f.stressor_a, f.stressor_b) for f in findings),
              "in_finding": s in used} for s in STRESSORS if s in {p[k] for p in run.pairs for k in ("a", "b")}]
    edges = [{"source": f.stressor_a, "target": f.stressor_b, "value": f.effect_size, "type": f.interaction_type, "status": f.status,
              "finding_id": f.id} for f in findings]
    return {"dataset_id": dataset_id, "run_id": run.id, "nodes": nodes, "edges": edges}
