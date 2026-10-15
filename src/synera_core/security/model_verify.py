"""Model registration and verification.

``register_model`` records, in the ledger, the SHA-256 of the weights file, library versions, seed, the hash
of the training data, a reference metric on a fixed hold-out set and the hash of the model's predictions on
a fixed probe set. ``verify_model`` re-hashes the weights, re-evaluates the model on the same hold-out and
probe set and reports every check, so swapped or modified weights are detected even when the file hash is
(wrongly) trusted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

from synera_core.provenance.hashing import sha256_file, sha256_obj
from synera_core.provenance.ledger import Block, Ledger

Predict = Callable[[Path, np.ndarray], np.ndarray]


def _round_pred(y: np.ndarray) -> list[float]:
    return [float(f"{v:.8g}") for v in np.asarray(y, float).ravel()]


def register_model(ledger: Ledger, model_path: Path, predict_fn: Predict, probe_X: np.ndarray, holdout_X: np.ndarray,
                   holdout_y: np.ndarray, training_data_hash: str, seed: int, versions: dict[str, str] | None = None) -> dict[str, Any]:
    """Register a trained model; returns the reference record that was written to the ledger."""
    ref = {
        "weights_sha256": sha256_file(model_path),
        "training_data_hash": training_data_hash,
        "seed": seed,
        "versions": versions or {},
        "holdout_rmse": float(np.sqrt(np.mean((predict_fn(model_path, holdout_X) - holdout_y) ** 2))),
        "probe_prediction_hash": sha256_obj(_round_pred(predict_fn(model_path, probe_X))),
    }
    blk: Block = ledger.append("MODEL_REGISTERED", {"path": model_path.name, **ref}, artifact_hashes=[ref["weights_sha256"]])
    return {**ref, "block_index": blk.index}


def verify_model(model_path: Path, predict_fn: Predict, reference: dict[str, Any], probe_X: np.ndarray, holdout_X: np.ndarray,
                 holdout_y: np.ndarray, tolerance: float = 1e-6) -> dict[str, Any]:
    """Run every model check against the registered ``reference``; ``ok`` only if all pass."""
    weights = sha256_file(model_path)
    try:
        rmse = float(np.sqrt(np.mean((predict_fn(model_path, holdout_X) - holdout_y) ** 2)))
        pred_hash = sha256_obj(_round_pred(predict_fn(model_path, probe_X)))
        err = None
    except Exception as exc:  # noqa: BLE001 - a tampered file may not even load
        rmse, pred_hash, err = float("nan"), "", str(exc)
    checks = [
        {"name": "weights_hash", "ok": weights == reference["weights_sha256"],
         "detail": "weights file SHA-256 equals the registered hash" if weights == reference["weights_sha256"]
         else f"registered {reference['weights_sha256'][:12]}..., found {weights[:12]}..."},
        {"name": "holdout_metric", "ok": err is None and abs(rmse - reference["holdout_rmse"]) <= tolerance,
         "detail": f"hold-out RMSE {rmse:.6g} vs registered {reference['holdout_rmse']:.6g} (tolerance {tolerance:g})" if err is None else err},
        {"name": "probe_predictions", "ok": pred_hash == reference["probe_prediction_hash"],
         "detail": "prediction hash on the fixed probe set is identical" if pred_hash == reference["probe_prediction_hash"]
         else "predictions on the fixed probe set changed"},
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "message": "Model verified" if all(c["ok"] for c in checks) else "Model hash / behaviour mismatch (weights swapped or modified)"}
