"""Service health and the read-only evidence ledger. The API can never append to or alter the ledger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.merkle import verify_proof

from backend.app.core.config import API_VERSION, offline
from backend.app.core.deps import get_ledger
from backend.app.db.database import get_session
from backend.app.db.models import SCHEMA_VERSION, Dataset, Finding, Run

router = APIRouter()


def _block(b) -> dict:
    d = b.to_dict()
    d["artifact_count"] = len(b.payload.get("artifact_hashes", []))
    return d


@router.get("/health", tags=["System"], summary="Service, database and ledger status")
def health(ledger: Ledger = Depends(get_ledger), session: Session = Depends(get_session)):
    v = ledger.verify()
    return {
        "status": "ok", "version": API_VERSION, "offline": offline(),
        "pipeline": "available", "database": {"ok": True, "schema_version": SCHEMA_VERSION},
        "ledger": {"height": v["height"], "chain_valid": v["valid"], "head": v["head"], "signer": ledger.signer,
                   "issues": v["issues"][:5]},
        "counts": {
            "datasets": session.exec(select(func.count()).select_from(Dataset)).one(),
            "runs": session.exec(select(func.count()).select_from(Run)).one(),
            "findings": session.exec(select(func.count()).select_from(Finding)).one(),
        },
    }


@router.get("/ledger/head", tags=["Ledger"], summary="Latest block")
def ledger_head(ledger: Ledger = Depends(get_ledger)):
    h = ledger.head()
    return _block(h) if h else {}


@router.get("/ledger/blocks", tags=["Ledger"], summary="Blocks (newest first by default)")
def ledger_blocks(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), order: str = Query("desc", pattern="^(asc|desc)$"),
                  block_type: str | None = None, ledger: Ledger = Depends(get_ledger)):
    blocks = list(ledger.iter_blocks())
    if block_type:
        blocks = [b for b in blocks if b.block_type == block_type]
    total = len(blocks)
    blocks = blocks[::-1] if order == "desc" else blocks
    return {"total": total, "items": [_block(b) for b in blocks[offset:offset + limit]]}


@router.get("/ledger/blocks/{index}", tags=["Ledger"], summary="One block with its full payload")
def ledger_block(index: int, ledger: Ledger = Depends(get_ledger)):
    try:
        return _block(ledger.get(index))
    except Exception:  # noqa: BLE001
        raise HTTPException(404, f"block {index} not found")


@router.get("/ledger/verify", tags=["Ledger"], summary="Verify the whole chain (links, hashes, Merkle roots, signatures)")
def ledger_verify(ledger: Ledger = Depends(get_ledger)):
    return ledger.verify()


@router.get("/ledger/proof/{artifact_hash}", tags=["Ledger"], summary="Merkle inclusion proof of an artifact hash")
def ledger_proof(artifact_hash: str, ledger: Ledger = Depends(get_ledger)):
    if len(artifact_hash) != 64 or any(c not in "0123456789abcdef" for c in artifact_hash.lower()):
        raise HTTPException(400, "artifact_hash must be a 64-character hex SHA-256")
    matches = ledger.find_by_artifact(artifact_hash.lower())
    if not matches:
        raise HTTPException(404, "artifact hash is not recorded in the ledger")
    block, proof = matches[0]
    return {"artifact_hash": artifact_hash.lower(), "block_index": block.index, "block_type": block.block_type,
            "merkle_root": block.merkle_root,
            "merkle_proof": [{"side": s, "hash": h} for s, h in proof],
            "verified": verify_proof(artifact_hash.lower(), proof, block.merkle_root)}
