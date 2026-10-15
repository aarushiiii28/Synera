"""Findings: the registry, the evidence bundle, and the live VERIFIED gate."""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select
from synera_core.pipeline.gates import run_gates
from synera_core.pipeline.registry import get_registry
from synera_core.provenance.ledger import Ledger
from synera_core.security.pipeline_integrity import current_src_tree_hash

from backend.app.core.deps import get_ledger
from backend.app.db.database import get_session
from backend.app.db.models import Dataset, Finding, Run
from backend.app.services.persist import finding_dict

router = APIRouter(prefix="/findings", tags=["Findings"])

SORTS = {
    "q_value": Finding.q_value.asc(), "-q_value": Finding.q_value.desc(),
    "effect_size": Finding.effect_size.asc(), "-effect_size": Finding.effect_size.desc(),
    "status": Finding.status.asc(), "created": Finding.created_at.desc(),
}


def _get(session: Session, finding_id: str) -> Finding:
    row = session.get(Finding, finding_id)
    if not row:
        raise HTTPException(404, f"finding '{finding_id}' not found")
    return row


@router.get("", summary="Findings registry with filters, sorting and pagination")
def list_findings(
    status: Literal["CANDIDATE", "VALIDATED", "VERIFIED", "BLOCKED", "REJECTED"] | None = None,
    track: Literal["A", "B"] | None = None,
    type: Literal["SYNERGISTIC", "ANTAGONISTIC", "NONLINEAR"] | None = None,
    provenance: Literal["REAL", "SIMULATED"] | None = None,
    dataset_id: str | None = None,
    q: str | None = Query(None, max_length=60, description="substring of a stressor or gene name"),
    sort: str = "-effect_size", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    query = select(Finding)
    for col, val in ((Finding.status, status), (Finding.track, track), (Finding.interaction_type, type),
                     (Finding.provenance, provenance), (Finding.dataset_id, dataset_id)):
        if val:
            query = query.where(col == val)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Finding.stressor_a.ilike(like), Finding.stressor_b.ilike(like), Finding.feature.ilike(like)))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(query.order_by(SORTS.get(sort, SORTS["-effect_size"])).offset(offset).limit(limit)).all()
    by = dict(session.exec(select(Finding.status, func.count()).group_by(Finding.status)).all())
    return {"total": total, "items": [finding_dict(r) for r in rows],
            "counts": {s: by.get(s, 0) for s in ("CANDIDATE", "VALIDATED", "VERIFIED", "BLOCKED", "REJECTED")}}


@router.get("/{finding_id}", summary="Full evidence bundle")
def get_finding(finding_id: str, session: Session = Depends(get_session)):
    row = _get(session, finding_id)
    run = session.get(Run, row.run_id)
    ds = session.get(Dataset, row.dataset_id)
    out = finding_dict(row)
    out["dataset"] = ds.model_dump(exclude={"qc"}) if ds else None
    out["run"] = ({"id": run.id, "status": run.status, "config_hash": run.config_hash, "result_hash": run.result_hash,
                   "dataset_hash": run.dataset_hash, "ledger_block": run.ledger_block, "replay": run.replay,
                   "params": run.params, "stage_counts": run.stage_counts, "runtime_s": run.runtime_s} if run else None)
    out["config"] = row.config
    return out


@router.post("/{finding_id}/verify", summary="Re-run every VERIFIED gate now and report pass/fail with reasons")
def verify_finding(finding_id: str, session: Session = Depends(get_session), ledger: Ledger = Depends(get_ledger)):
    row = _get(session, finding_id)
    run = session.get(Run, row.run_id)
    spec = get_registry().get(row.dataset_id)
    f = {**finding_dict(row), "dataset_hashes": row.dataset_hashes, "config": row.config, "evidence_level": row.evidence_level}
    run_ctx = {"replay": run.replay if run else None, "src_tree_hash": run.src_tree_hash if run else None}
    g = run_gates(f, ledger, spec.abs_path if spec else None, row.dataset_hashes.get(row.dataset_id), run_ctx, current_src_tree_hash())
    previous = row.status
    if g["new_status"] == "BLOCKED":
        row.status = "BLOCKED"
    elif g["new_status"] == "VERIFIED":
        row.status = "VERIFIED"
    row.gates = g["gates"]
    row.history = [*row.history, f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC: re-verified: {previous} -> {row.status}"]
    session.add(row)
    session.commit()
    return {"id": finding_id, "previous_status": previous, "new_status": row.status, "allowed": g["allowed"],
            "reasons": g["reasons"], "gates": g["gates"], "verdict": g["verdict"]}


@router.get("/{finding_id}/surface", summary="Response surface: additive expectation vs fitted surface vs gap")
def finding_surface(finding_id: str, session: Session = Depends(get_session)):
    row = _get(session, finding_id)
    if not row.surface:
        raise HTTPException(404, "this finding has no continuous response surface (factorial design)")
    return {**row.surface, "type": row.interaction_type, "provenance": row.provenance}


@router.get("/{finding_id}/forest", summary="Effect estimates with intervals across analyses")
def finding_forest(finding_id: str, session: Session = Depends(get_session)):
    row = _get(session, finding_id)
    e = row.effect
    rows = [{"name": "Bilinear interaction coefficient (all data)", "effect": e.get("b_AB"), "ci_low": e.get("ci_low"),
             "ci_high": e.get("ci_high"), "unit": "outcome SD" if row.track == "B" else "log2"}]
    if e.get("effect_size") is not None:
        rows.append({"name": "Interaction surface effect size (all data)", "effect": e["effect_size"], "ci_low": e.get("eff_ci_low"),
                     "ci_high": e.get("eff_ci_high"), "unit": "outcome SD"})
    rep = (row.replication or {}).get("halves") or {}
    for h, v in rep.items():
        rows.append({"name": f"City hold-out half {h}: joint test p = {v['p']:.2e}", "effect": None, "ci_low": None, "ci_high": None,
                     "p": v["p"], "cities": v.get("cities"), "unit": ""})
    return {"studies": rows, "methods": row.methods, "evidence_level": row.evidence_level}
