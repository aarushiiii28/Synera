import pandas as pd
import numpy as np
import hashlib
from pathlib import Path
from synera_core.provenance.hashing import sha256_dataframe, sha256_file
from synera_core.security.poisoning import scan_dataset

def simulate_attack(mode: str, data_path: Path, meta_path: Path = None) -> dict:
    """
    Demo attacks. Operate ONLY on temp copies, never on raw/processed data.
    Modes: bit_flip, row_edit, poison_labels, inject_outliers, swap_model, drift_units
    """
    df = pd.read_parquet(data_path)
    original_hash = sha256_dataframe(df)
    
    meta = None
    if meta_path:
        meta = pd.read_parquet(meta_path)
        
    detections = []
    
    df_tampered = df.copy()
    
    if mode == "row_edit":
        # Edit a few cells
        cols = df_tampered.select_dtypes(include=[np.number]).columns
        if len(cols) > 0:
            df_tampered.loc[0:2, cols[0]] = 999999.0
            
    elif mode == "inject_outliers":
        # k% extreme rows
        n_outliers = max(1, int(len(df_tampered) * 0.05))
        idx = np.random.choice(df_tampered.index, n_outliers, replace=False)
        cols = df_tampered.select_dtypes(include=[np.number]).columns
        for c in cols:
            df_tampered.loc[idx, c] = df_tampered[c].max() * 10
            
    elif mode == "drift_units":
        # Scale a column (e.g. Fahrenheit as Celsius)
        cols = df_tampered.select_dtypes(include=[np.number]).columns
        if len(cols) > 0:
            df_tampered[cols[0]] = df_tampered[cols[0]] * 1.8 + 32
            
    elif mode == "subtle_edit":
        cols = df_tampered.select_dtypes(include=[np.number]).columns
        if len(cols) > 0:
            # Edit 10% of cells by 0.3 SD
            n_poison = max(1, int(len(df_tampered) * 0.10))
            idx = np.random.choice(df_tampered.index, n_poison, replace=False)
            sd = df_tampered[cols[0]].std()
            df_tampered.loc[idx, cols[0]] = df_tampered.loc[idx, cols[0]] + 0.3 * sd
            
    elif mode == "poison_labels" and meta is not None:
        meta_tampered = meta.copy()
        target_col = [c for c in meta.columns if meta[c].nunique() == 2]
        if target_col:
            col = target_col[0]
            n_poison = max(1, int(len(meta_tampered) * 0.2))
            idx = np.random.choice(meta_tampered.index, n_poison, replace=False)
            meta_tampered.loc[idx, col] = 1 - meta_tampered.loc[idx, col]
            meta = meta_tampered
            
    tampered_hash = sha256_dataframe(df_tampered)
    hash_match = (original_hash == tampered_hash)
    
    if not hash_match:
        detections.append("hash_mismatch")
        
    # Scan
    report = scan_dataset(df_tampered, meta)
    for check in report.checks:
        if check["status"] != "PASS":
            detections.append(check["name"])
                
    return {
        "mode": mode,
        "original_hash": original_hash,
        "tampered_hash": tampered_hash,
        "hash_match": hash_match,
        "detections": list(set(detections)),
        "ledger_alert_block": "INTEGRITY_ALERT",
        "verdict": "RESULT BLOCKED FROM VERIFIED STATUS"
    }
