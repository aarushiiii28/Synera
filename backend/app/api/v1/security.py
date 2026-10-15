"""Security: the tamper simulator (temporary copies only) and security reports."""

from __future__ import annotations

import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from synera_core.pipeline.registry import get_registry
from synera_core.provenance.ledger import Ledger
from synera_core.security.tamper_sim import DESCRIPTIONS, MODES, simulate_attack

from backend.app.core.config import SIMULATE_RATE_LIMIT_PER_MIN
from backend.app.core.deps import get_ledger, read_result_json
from backend.app.db.database import get_session
from backend.app.db.models import SecurityReport

router = APIRouter(prefix="/security", tags=["Security"])
_calls: deque[float] = deque()


class TamperRequest(BaseModel):
    dataset_id: str
    mode: str
    magnitude: float = Field(0.05, ge=0.001, le=0.5, description="Fraction of rows/cells affected")
    seed: int = Field(0, ge=0, le=10_000)


@router.get("/modes", summary="Attack modes the simulator supports")
def modes():
    return [{"mode": m, "description": DESCRIPTIONS[m]} for m in MODES]


@router.post("/simulate-tamper", summary="Run an attack on a temporary copy and report what the integrity layer detects")
def simulate_tamper(req: TamperRequest, ledger: Ledger = Depends(get_ledger)):
    now = time.time()
    while _calls and now - _calls[0] > 60:
        _calls.popleft()
    if len(_calls) >= SIMULATE_RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "too many simulations; try again in a minute")
    _calls.append(now)
    reg = get_registry()
    if req.dataset_id not in reg:
        raise HTTPException(404, f"dataset '{req.dataset_id}' not found")
    if req.mode not in MODES:
        raise HTTPException(400, f"unsupported mode '{req.mode}'; choose one of {MODES}")
    try:
        return simulate_attack(req.dataset_id, req.mode, req.magnitude, req.seed, ledger)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))


@router.get("/false-alarm-rates", summary="Measured clean-data false-alarm rate and attack detection rates per detector")
def false_alarm_rates():
    bench = read_result_json("benchmark.json") or {}
    sec = bench.get("security")
    if not sec:
        return {"available": False}
    return {"available": True, "clean_false_alarm_rate": sec["clean_false_alarm_rate"], "attacks": sec["attacks"],
            "clean_false_alarm_counts": sec.get("clean_false_alarm_counts", {}), "clean_false_alarm_ci95": sec.get("clean_false_alarm_ci95", {}),
            "clean_seeds": sec.get("clean_seeds"),
            "hash_only_attacks": sec["hash_only_attacks"], "trials_per_cell": sec["trials_per_cell"],
            "policy": "Only integrity-critical checks (hash, ledger chain, physical range, replay) can block a result; "
                      "statistical detectors are advisory."}


@router.get("/reports", summary="Latest security report per dataset")
def reports(dataset_id: str | None = None, session: Session = Depends(get_session)):
    q = select(SecurityReport).order_by(SecurityReport.created_at.desc())
    if dataset_id:
        q = q.where(SecurityReport.dataset_id == dataset_id)
    return session.exec(q).all()


@router.get("/reports/{report_id}", summary="One security report")
def report(report_id: str, session: Session = Depends(get_session)):
    rep = session.get(SecurityReport, report_id)
    if not rep:
        raise HTTPException(404, "report not found")
    return rep
