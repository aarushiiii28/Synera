"""Engine report card and experiment history. The report is served exactly as measured, limitations included."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from backend.app.core.deps import read_result_json
from backend.app.db.database import get_session
from backend.app.db.models import ExperimentSummary, Run

router = APIRouter(tags=["Benchmark"])


@router.get("/benchmark/results", summary="Engine report card (SIMULATED benchmark), unedited, with limitations")
def benchmark_results():
    rep = read_result_json("benchmark.json")
    if not rep:
        return {"available": False, "provenance": "SIMULATED",
                "limitations": ["The benchmark has not been run. Run  python scripts/run_benchmark.py  (about 30-40 minutes)."]}
    return {"available": True, **rep}


@router.get("/experiments", summary="Experiment history: every run with its config hash, result hash and ledger block")
def experiments(session: Session = Depends(get_session)):
    rows = session.exec(select(ExperimentSummary, Run).join(Run, Run.id == ExperimentSummary.run_id)
                        .order_by(ExperimentSummary.created_at.desc())).all()
    return [{"run_id": e.run_id, "dataset_id": e.dataset_id, "status": e.status, "config_hash": e.config_hash,
             "result_hash": e.result_hash, "ledger_block": e.ledger_block, "runtime_s": e.runtime_s, "created_at": e.created_at,
             "replay_matches": (r.replay or {}).get("matches"), "summary": r.summary, "params": r.params} for e, r in rows]
