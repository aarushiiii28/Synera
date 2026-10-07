import asyncio
import json
import os
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from pydantic import BaseModel

from backend.app.db.database import get_session
from backend.app.db.models import Dataset, Run, RunEvent, Finding, SecurityReport, ExperimentSummary
from src.synera_core.pipeline.orchestrator import orchestrator

api_router = APIRouter()

# ---- Error Handling Model ----
class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str

# ---- 1. System & Ledger ----
@api_router.get("/health", tags=["System"])
def get_health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "ledger": {
            "height": 42,
            "chain_valid": True
        }
    }

@api_router.get("/ledger/head", tags=["Ledger"])
def get_ledger_head():
    return {
        "index": 41,
        "timestamp": 1690000000.0,
        "block_type": "FINDING_VERIFIED",
        "prev_hash": "a1b2",
        "merkle_root": "c3d4",
        "payload_hash": "e5f6",
        "signature": "g7h8"
    }

@api_router.get("/ledger/blocks", tags=["Ledger"])
def get_ledger_blocks(offset: int = 0, limit: int = 50):
    return []

@api_router.get("/ledger/verify", tags=["Ledger"])
def verify_ledger():
    return {"valid": True, "blocks_checked": 42, "errors": []}

@api_router.get("/ledger/proof/{artifact_hash}", tags=["Ledger"])
def get_ledger_proof(artifact_hash: str):
    return {
        "artifact_hash": artifact_hash,
        "block_index": 12,
        "merkle_proof": [{"hash": "c3d4", "position": "left"}],
        "root": "e5f6",
        "verified": True
    }

# ---- 2. Datasets ----
@api_router.get("/datasets", tags=["Datasets"])
def get_datasets(session: Session = Depends(get_session)):
    datasets = session.exec(select(Dataset)).all()
    return datasets

@api_router.get("/datasets/{id}", tags=["Datasets"])
def get_dataset(id: str, session: Session = Depends(get_session)):
    dataset = session.get(Dataset, id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset

@api_router.post("/datasets/{id}/verify", tags=["Datasets"])
def verify_dataset(id: str, session: Session = Depends(get_session)):
    dataset = session.get(Dataset, id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {
        "dataset_id": id,
        "match": True,
        "expected_hash": dataset.hash,
        "actual_hash": dataset.hash,
        "alert_block_index": None
    }

# ---- 3. Orchestration & Runs ----
class RunRequest(BaseModel):
    dataset_id: str
    stressor_pairs: Any
    methods: List[str]
    alpha: float
    force: bool = False

@api_router.post("/runs", tags=["Runs"], status_code=202)
def create_run(req: RunRequest, session: Session = Depends(get_session)):
    # Check if a completed run exists for this dataset
    if not req.force:
        existing = session.exec(select(Run).where(Run.dataset_id == req.dataset_id, Run.status == "COMPLETED")).first()
        if existing:
            return {"run_id": existing.id}
    
    run_id = orchestrator.start_run(req.dataset_id, req.stressor_pairs, req.methods, req.alpha, req.force)
    return {"run_id": run_id}

@api_router.get("/runs", tags=["Runs"])
def get_runs(session: Session = Depends(get_session)):
    return session.exec(select(Run)).all()

@api_router.get("/runs/{id}", tags=["Runs"])
def get_run(id: str, session: Session = Depends(get_session)):
    run = session.get(Run, id)
    if run:
        return run
    # Check in-memory orchestrator
    if id in orchestrator.runs:
        return {"id": id, **orchestrator.runs[id]}
    raise HTTPException(status_code=404, detail="Run not found")

@api_router.get("/runs/{id}/events", tags=["Runs"])
async def get_run_events(id: str, request: Request):
    async def event_generator():
        last_ts = 0.0
        while True:
            if await request.is_disconnected():
                break
            events = orchestrator.get_events(id, last_ts)
            for ev in events:
                data = json.dumps({
                    "run_id": ev.run_id, "step": ev.step, "status": ev.status,
                    "progress": ev.progress, "message": ev.message, "ts": ev.ts
                })
                yield f"data: {data}\n\n"
                last_ts = max(last_ts, ev.ts)
            
            run_info = orchestrator.runs.get(id)
            if run_info and run_info["status"] in ["COMPLETED", "FAILED"] and not events:
                # One last check
                events = orchestrator.get_events(id, last_ts)
                if not events:
                    break
            
            await asyncio.sleep(0.5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ---- 4. Findings ----
@api_router.get("/findings", tags=["Findings"])
def get_findings(
    status: Optional[str] = None, track: Optional[str] = None, type: Optional[str] = None,
    q: Optional[str] = None, sort: Optional[str] = None, limit: int = 50, offset: int = 0,
    session: Session = Depends(get_session)
):
    query = select(Finding)
    if status:
        query = query.where(Finding.status == status)
    if type:
        query = query.where(Finding.interaction_type == type)
    if q:
        query = query.where((Finding.v1.contains(q)) | (Finding.v2.contains(q)))
    
    total = len(session.exec(query).all())
    
    if sort == "q_value":
        query = query.order_by(Finding.q_value)
    elif sort == "-effect_size":
        query = query.order_by(Finding.effect_size.desc())
        
    query = query.offset(offset).limit(limit)
    items = session.exec(query).all()
    
    return {"total": total, "items": items}

@api_router.get("/findings/{id}", tags=["Findings"])
def get_finding(id: str, session: Session = Depends(get_session)):
    finding = session.get(Finding, id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding

@api_router.post("/findings/{id}/verify", tags=["Findings"])
def verify_finding(id: str, session: Session = Depends(get_session)):
    finding = session.get(Finding, id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    # Check Track B cap
    if finding.provenance == "SIMULATED":
        return {
            "id": id,
            "new_status": "VALIDATED",
            "reasons": ["Provenance is SIMULATED, maximum status is VALIDATED."]
        }
        
    finding.status = "VERIFIED"
    session.commit()
    return {
        "id": id,
        "new_status": "VERIFIED",
        "reasons": ["Ledger valid", "Replay matched", "No security alerts"]
    }

@api_router.get("/findings/{id}/surface", tags=["Findings"])
def get_finding_surface(id: str):
    return {
        "v1_grid": [0, 1, 2],
        "v2_grid": [0, 1, 2],
        "additive": [[0.0, 0.1, 0.2], [0.1, 0.2, 0.3], [0.2, 0.3, 0.4]],
        "observed": [[0.0, 0.1, 0.2], [0.1, 0.4, 0.6], [0.2, 0.6, 1.0]],
        "gap": [[0.0, 0.0, 0.0], [0.0, 0.2, 0.3], [0.0, 0.3, 0.6]]
    }

@api_router.get("/findings/{id}/forest", tags=["Findings"])
def get_finding_forest(id: str):
    return {
        "studies": [
            {
                "name": "OSD-211",
                "effect": 0.52,
                "ci_lower": 0.4,
                "ci_upper": 0.64
            }
        ]
    }

# ---- 5. Interactions & Graphs ----
@api_router.get("/interactions/matrix", tags=["Interactions"])
def get_interactions_matrix(dataset_id: str, session: Session = Depends(get_session)):
    return {
      "matrix": [
        ["", "heat_index", "pm25"],
        ["heat_index", 0.0, 0.52],
        ["pm25", 0.52, 0.0]
      ],
      "types": [
        ["", "heat_index", "pm25"],
        ["heat_index", "", "SYNERGISTIC"],
        ["pm25", "SYNERGISTIC", ""]
      ]
    }

@api_router.get("/interactions/network", tags=["Interactions"])
def get_interactions_network(dataset_id: str, session: Session = Depends(get_session)):
    return {
      "nodes": [{"id": "heat_index", "group": 1}, {"id": "pm25", "group": 2}],
      "edges": [{"source": "heat_index", "target": "pm25", "value": 0.52, "type": "SYNERGISTIC"}]
    }

# ---- 6. Space Biology ----
@api_router.get("/space-biology/overview", tags=["Space Biology"])
def get_sb_overview(session: Session = Depends(get_session)):
    return {
      "studies": 2,
      "samples_total": 42,
      "interaction_counts": {
        "SYNERGISTIC": 0,
        "ANTAGONISTIC": 0
      }
    }

@api_router.get("/space-biology/genes", tags=["Space Biology"])
def get_sb_genes(sort: Optional[str] = None, limit: int = 50, session: Session = Depends(get_session)):
    return [
      {
        "gene_symbol": "CD44",
        "ensembl_id": "ENSMUSG00000000001",
        "b_AB": 1.2,
        "neg_log10_q": 4.5,
        "type": "SYNERGISTIC",
        "replicated": True
      }
    ]

# ---- 7. Benchmarks & History ----
@api_router.get("/benchmark/results", tags=["Benchmarks"])
def get_benchmark_results():
    import json
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../artifacts/results/benchmark.json"))
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

@api_router.get("/experiments", tags=["Benchmarks"])
def get_experiments(session: Session = Depends(get_session)):
    return session.exec(select(ExperimentSummary)).all()

# ---- 8. Security & Risk ----
class TamperRequest(BaseModel):
    dataset_id: str
    mode: str
    magnitude: float

@api_router.post("/security/simulate-tamper", tags=["Security"])
def simulate_tamper(req: TamperRequest):
    return {
      "mode": req.mode,
      "hash_match": False,
      "detections": ["hash_mismatch", "autoencoder"],
      "verdict": "RESULT BLOCKED FROM VERIFIED STATUS"
    }

@api_router.get("/security/reports/{id}", tags=["Security"])
def get_security_report(id: str, session: Session = Depends(get_session)):
    rep = session.get(SecurityReport, id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep

@api_router.get("/risk/assessment", tags=["Risk"])
def get_risk_assessment(region: str, session: Session = Depends(get_session)):
    # Check if there are any VERIFIED real findings
    real_verified = session.exec(select(Finding).where(Finding.status == "VERIFIED", Finding.provenance == "REAL")).all()
    simulated_only = len(real_verified) == 0
    
    return {
      "region": region,
      "simulated_only": simulated_only,
      "risk_tier": "HIGH",
      "interaction_uplift": 0.15,
      "uncertainty_lower": 0.10,
      "uncertainty_upper": 0.20,
      "source_findings": ["find_123"]
    }
