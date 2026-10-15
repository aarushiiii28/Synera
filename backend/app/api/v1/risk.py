"""Action layer: compound environmental risk from validated interaction findings, with its receipt."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from synera_core.data.cities import CITIES
from synera_core.risk.assessment import evaluate_risk

from backend.app.core.config import offline
from backend.app.db.database import get_session
from backend.app.db.models import Finding, Run

router = APIRouter(prefix="/risk", tags=["Risk"])


def finite_or_none(x):
    """Recursively replace NaN/inf (missing forecast fields) with None so the response is valid JSON."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: finite_or_none(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [finite_or_none(v) for v in x]
    return x


@router.get("/regions", summary="Regions with coordinates")
def regions():
    return [{"id": name, **c} for name, c in CITIES.items()]


@router.get("/assessment", summary="Compound-risk brief for a region (VALIDATED/VERIFIED findings only)")
def assessment(region: str, session: Session = Depends(get_session)):
    if region not in CITIES:
        raise HTTPException(404, f"unknown region '{region}'; choose one of {sorted(CITIES)}")
    rows = session.exec(select(Finding).where(Finding.status.in_(("VALIDATED", "VERIFIED")), Finding.track == "B")).all()
    findings = [{"id": r.id, "provenance": r.provenance, "status": r.status, "stressors": [r.stressor_a, r.stressor_b],
                 "surface": r.surface, "effect": r.effect, "run_id": r.run_id, "type": r.interaction_type} for r in rows]
    out = evaluate_risk(region, findings, offline=offline())
    out["findings"] = [{"id": f["id"], "stressors": f["stressors"], "type": f["type"], "status": f["status"], "provenance": f["provenance"]}
                       for f in findings if f["id"] in out["source_findings"]]
    runs = {f["run_id"] for f in findings if f["id"] in out["source_findings"]}
    out["receipt"] = [{"run_id": r.id, "config_hash": r.config_hash, "result_hash": r.result_hash, "dataset_hash": r.dataset_hash,
                       "ledger_block": r.ledger_block, "replay_matches": (r.replay or {}).get("matches")}
                      for r in (session.get(Run, rid) for rid in runs) if r]
    out["banner"] = ("SIMULATED DEMONSTRATION: every finding behind this brief comes from the simulated benchmark; "
                     "no verified real-world interaction supports it." if out.get("simulated_only") else None)
    return finite_or_none(out)
