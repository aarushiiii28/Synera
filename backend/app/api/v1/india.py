"""India live intelligence: live readings for Indian cities, run through the SYNERA engine, with ranked actions and the evidence behind them.

Nothing here is simulated. When a provider fails the response says so and carries no invented value (the last good copy is marked ``stale``).
See docs/INDIA_LIVE.md for the data sources, environment variables and what each number means.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from synera_core.india import service
from synera_core.india.cities import BY_ID, CITIES

from backend.app.db.database import get_session
from backend.app.db.models import Finding

router = APIRouter(prefix="/india", tags=["India live"])


def _clean(x):
    """NaN / inf become null so the response is valid JSON."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


@router.get("/cities", summary="Supported cities")
def cities():
    return CITIES


@router.get("/overview", summary="Live summary of every supported city: map markers, layers, national hotspots and alerts")
def overview():
    return _clean(service.overview())


@router.get("/city/{city_id}", summary="One city: readings, forecast, SYNERA engine output, ranked recommendations, explanation")
def city(city_id: str, session: Session = Depends(get_session)):
    if city_id not in BY_ID:
        raise HTTPException(404, f"unknown city '{city_id}'")
    rows = session.exec(select(Finding).where(Finding.status.in_(("VALIDATED", "VERIFIED")), Finding.track == "D")).all()
    findings = [{"id": r.id, "provenance": r.provenance, "status": r.status, "stressors": [r.stressor_a, r.stressor_b], "surface": r.surface, "effect": r.effect,
                 "dataset_id": r.dataset_id, "type": r.interaction_type, "evidence_level": r.evidence_level} for r in rows]
    return _clean(service.city_detail(city_id, findings))
