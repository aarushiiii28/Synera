"""Runs: start the pipeline, list runs, stream progress (Server-Sent Events)."""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from synera_core.pipeline.orchestrator import STEPS
from synera_core.pipeline.registry import get_registry
from synera_core.provenance.ledger import Ledger

from backend.app.core.config import MAX_N_BOOT, MIN_N_BOOT
from backend.app.core.deps import get_ledger
from backend.app.db.database import engine, get_session
from backend.app.db.models import Run, RunEvent
from backend.app.services.runs import RunConflict, manager

router = APIRouter(prefix="/runs", tags=["Runs"])


class RunRequest(BaseModel):
    dataset_id: str
    quick: bool = Field(False, description="Fewer bootstrap resamples (faster demo run); recorded in the run configuration")
    alpha: float = Field(0.05, gt=0.0, le=0.2)
    n_boot: int | None = Field(None, ge=MIN_N_BOOT, le=MAX_N_BOOT)
    force: bool = Field(False, description="Re-run even if an identical finished run exists")


@router.get("/steps", summary="The ordered pipeline steps")
def steps():
    return [{"step": i + 1, "name": n, "label": label} for i, (n, label) in enumerate(STEPS)]


@router.post("", status_code=202, summary="Start (or reuse) a run")
def create_run(req: RunRequest, session: Session = Depends(get_session), ledger: Ledger = Depends(get_ledger)):
    reg = get_registry()
    if req.dataset_id not in reg:
        raise HTTPException(404, f"dataset '{req.dataset_id}' not found")
    if not reg[req.dataset_id].runnable:
        raise HTTPException(400, f"'{req.dataset_id}' has no outcome variable; run the analysis on 'benchmark_track_b' or an OSDR study")
    overrides: dict = {"alpha": req.alpha, "quick": req.quick}
    if req.n_boot:
        overrides["n_boot"] = req.n_boot
    try:
        run_id, reused = manager.start(session, ledger, req.dataset_id, overrides, req.force)
    except RunConflict as exc:
        raise HTTPException(409, str(exc))
    return {"run_id": run_id, "reused": reused}


@router.get("", summary="Runs, newest first")
def list_runs(dataset_id: str | None = None, status: Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED"] | None = None,
              session: Session = Depends(get_session)):
    q = select(Run).order_by(Run.created_at.desc())
    if dataset_id:
        q = q.where(Run.dataset_id == dataset_id)
    if status:
        q = q.where(Run.status == status)
    rows = session.exec(q).all()
    return [{k: v for k, v in r.model_dump().items() if k not in ("pairs", "security", "consistency")} for r in rows]


@router.get("/{run_id}", summary="One run with its steps and stage counts")
def get_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(404, f"run '{run_id}' not found")
    events = session.exec(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id)).all()
    return {**run.model_dump(), "events": [e.model_dump() for e in events], "steps": [n for n, _ in STEPS]}


@router.get("/{run_id}/events", summary="Server-Sent Events: step-by-step progress with measured durations")
async def run_events(run_id: str, request: Request):
    with Session(engine) as s:
        if not s.get(Run, run_id):
            raise HTTPException(404, f"run '{run_id}' not found")

    async def gen():
        last = 0
        idle_after_done = 0
        while True:
            if await request.is_disconnected():
                break
            with Session(engine) as s:
                evs = s.exec(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > last).order_by(RunEvent.id)).all()
                run = s.get(Run, run_id)
            for e in evs:
                last = e.id
                yield f"data: {json.dumps({**e.model_dump()})}\n\n"
            if run and run.status != "RUNNING":
                idle_after_done += 1
                if not evs and idle_after_done >= 2:
                    yield f"event: end\ndata: {json.dumps({'run_id': run_id, 'status': run.status})}\n\n"
                    break
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
