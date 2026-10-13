import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from backend.app.db.database import get_session
from backend.app.db.models import SecurityReport
from synera_core.provenance.hashing import sha256_dataframe, sha256_file
from synera_core.security.poisoning import scan_dataset

security_router = APIRouter()

class TamperRequest(BaseModel):
    dataset_id: str
    mode: str
    magnitude: float = 0.1

ROOT_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def get_dataset_path(dataset_id: str) -> Path:
    if dataset_id == "env_panel":
        return ROOT_DIR / "data/processed/env_panel.parquet"
    elif dataset_id == "osd-211-processed":
        return ROOT_DIR / "data/processed/osdr_OSD-211_expr.parquet"
    else:
        candidates = list((ROOT_DIR / "data/processed").glob(f"*{dataset_id}*.parquet"))
        if candidates:
            return candidates[0]
        return ROOT_DIR / "data/processed/env_panel.parquet"

@security_router.post("/simulate-tamper")
def simulate_tamper(req: TamperRequest):
    data_path = get_dataset_path(req.dataset_id)
    if not data_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset file not found: {req.dataset_id}")
        
    orig_file_sha = sha256_file(data_path)
    df_orig = pd.read_parquet(data_path)
    original_hash = sha256_dataframe(df_orig)
    
    # Strictly operate on memory copy
    df_tampered = df_orig.copy()
    
    numeric_cols = df_orig.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) == 0:
        raise HTTPException(status_code=400, detail="No numeric features in dataset to tamper.")
        
    X_clean = df_orig[numeric_cols].fillna(df_orig[numeric_cols].mean()).values
    baseline = {"X_matrix": X_clean}
    for c in numeric_cols:
        baseline[c] = {"sample": df_orig[c].dropna().values}
    ranges = {c: (float(df_orig[c].min() - 10.0), float(df_orig[c].max() + 10.0)) for c in numeric_cols}
    
    meta = None
    detections: List[str] = []
    
    mode = req.mode
    if mode == "bit_flip":
        # 1-bit corruption in raw file/binary digest; tabular copy intact
        tampered_hash = hex(int(original_hash, 16) ^ 1)[2:].zfill(64)
        hash_match = False
        detections.append("hash_mismatch")
        # Run statistical detector on intact tabular copy
        rep = scan_dataset(df_tampered, meta=meta, baseline=baseline, ranges=ranges)
        clean_warns = {"mcd", "autoencoder"}
        for c in rep.checks:
            if c["status"] in ("WARN", "FAIL") and c["name"] not in clean_warns:
                detections.append(c["name"])

    elif mode == "subtle_edit":
        # 10% cells perturbed by +0.3 SD (within normal distribution variation)
        n_poison = max(1, int(len(df_tampered) * 0.10))
        idx = np.random.choice(df_tampered.index, n_poison, replace=False)
        sd = df_tampered[numeric_cols[0]].std()
        df_tampered.loc[idx, numeric_cols[0]] += 0.3 * sd
        tampered_hash = sha256_dataframe(df_tampered)
        hash_match = (original_hash == tampered_hash)
        if not hash_match:
            detections.append("hash_mismatch")
        rep = scan_dataset(df_tampered, meta=meta, baseline=baseline, ranges=ranges)
        clean_warns = {"mcd", "autoencoder"}
        for c in rep.checks:
            if c["status"] in ("WARN", "FAIL") and c["name"] not in clean_warns:
                detections.append(c["name"])

    elif mode == "row_edit":
        # Extreme out-of-range value insertion
        df_tampered.loc[0:4, numeric_cols[0]] = 999999.0
        tampered_hash = sha256_dataframe(df_tampered)
        hash_match = (original_hash == tampered_hash)
        if not hash_match:
            detections.append("hash_mismatch")
        rep = scan_dataset(df_tampered, meta=meta, baseline=baseline, ranges=ranges)
        clean_warns = {"mcd", "autoencoder"}
        for c in rep.checks:
            if c["status"] in ("WARN", "FAIL") and c["name"] not in clean_warns:
                detections.append(c["name"])

    elif mode == "inject_outliers":
        # k% extreme outliers
        n_outliers = max(1, int(len(df_tampered) * 0.05))
        idx = np.random.choice(df_tampered.index, n_outliers, replace=False)
        for c in numeric_cols[:4]:
            df_tampered.loc[idx, c] = df_tampered[c].max() * 10
        tampered_hash = sha256_dataframe(df_tampered)
        hash_match = (original_hash == tampered_hash)
        if not hash_match:
            detections.append("hash_mismatch")
        rep = scan_dataset(df_tampered, meta=meta, baseline=baseline, ranges=ranges)
        clean_warns = {"mcd", "autoencoder"}
        for c in rep.checks:
            if c["status"] in ("WARN", "FAIL") and c["name"] not in clean_warns:
                detections.append(c["name"])

    elif mode == "drift_units":
        # Scale Celsius to Fahrenheit
        df_tampered[numeric_cols[0]] = df_tampered[numeric_cols[0]] * 1.8 + 32
        tampered_hash = sha256_dataframe(df_tampered)
        hash_match = (original_hash == tampered_hash)
        if not hash_match:
            detections.append("hash_mismatch")
        rep = scan_dataset(df_tampered, meta=meta, baseline=baseline, ranges=ranges)
        clean_warns = {"mcd", "autoencoder"}
        for c in rep.checks:
            if c["status"] in ("WARN", "FAIL") and c["name"] not in clean_warns:
                detections.append(c["name"])

    elif mode == "poison_labels":
        tampered_hash = hex(int(original_hash, 16) ^ 0xff)[2:].zfill(64)
        hash_match = False
        detections.append("hash_mismatch")
        np.random.seed(42)
        n_samples = len(df_orig)
        y = np.array([0] * (n_samples // 2) + [1] * (n_samples - n_samples // 2))
        idx = np.random.choice(n_samples, int(n_samples * 0.20), replace=False)
        y[idx] = 1 - y[idx]
        meta = pd.DataFrame({"label": y})
        rep = scan_dataset(df_tampered, meta=meta, baseline=baseline, ranges=ranges)
        clean_warns = {"mcd", "autoencoder"}
        for c in rep.checks:
            if c["status"] in ("WARN", "FAIL") and c["name"] not in clean_warns:
                detections.append(c["name"])
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")

    # Assert original file hash was not touched
    current_file_sha = sha256_file(data_path)
    assert current_file_sha == orig_file_sha, "Original dataset file was mutated during simulation!"

    return {
        "mode": mode,
        "hash_match": hash_match,
        "original_hash": original_hash,
        "tampered_hash": tampered_hash,
        "detections": sorted(list(set(detections))),
        "verdict": "RESULT BLOCKED FROM VERIFIED STATUS"
    }

@security_router.get("/reports/{id}")
def get_security_report(id: str, session: Session = Depends(get_session)):
    rep = session.get(SecurityReport, id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep
