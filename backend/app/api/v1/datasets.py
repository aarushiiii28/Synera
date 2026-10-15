"""Datasets: what exists, its provenance tag, hash and QC; and a live integrity check."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from synera_core.pipeline.registry import get_registry
from synera_core.provenance.ledger import Ledger
from synera_core.security.integrity import IntegrityGuard

from backend.app.core.deps import get_ledger
from backend.app.db.database import get_session
from backend.app.db.models import Dataset

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("", summary="All registered datasets")
def list_datasets(session: Session = Depends(get_session)):
    return session.exec(select(Dataset).order_by(Dataset.track, Dataset.id)).all()


@router.get("/{dataset_id}", summary="One dataset with its QC summary")
def get_dataset(dataset_id: str, session: Session = Depends(get_session)):
    row = session.get(Dataset, dataset_id)
    if not row:
        raise HTTPException(404, f"dataset '{dataset_id}' not found")
    return row


@router.post("/{dataset_id}/verify", summary="Recompute the dataset hash and compare with the ledger record")
def verify_dataset(dataset_id: str, ledger: Ledger = Depends(get_ledger)):
    reg = get_registry()
    if dataset_id not in reg:
        raise HTTPException(404, f"dataset '{dataset_id}' not found")
    spec = reg[dataset_id]
    if not spec.abs_path.exists():
        raise HTTPException(404, f"dataset file for '{dataset_id}' is missing on disk")
    res = IntegrityGuard(ledger).check_dataset(spec.abs_path)
    return {"dataset_id": dataset_id, "match": res.ok, "expected_hash": res.expected_hash, "actual_hash": res.actual_hash,
            "ledger_block": res.block_index, "detail": res.detail, "checked_at": res.checked_at,
            "verdict": None if res.ok else "RESULT BLOCKED FROM VERIFIED STATUS"}
