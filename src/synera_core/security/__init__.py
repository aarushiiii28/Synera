"""Cybersecurity and data integrity subpackage."""

from synera_core.security.integrity import (
    IntegrityGuard,
    IntegrityResult,
    compute_file_sha256,
    guard_verified_status,
    verify_file_integrity,
)
from synera_core.security.model_verify import register_model, verify_model
from synera_core.security.pipeline_integrity import snapshot_pipeline, detect_code_drift, reproducibility_replay
from synera_core.security.poisoning import scan_dataset
from synera_core.security.tamper_sim import simulate_attack

__all__ = [
    "IntegrityGuard",
    "IntegrityResult",
    "compute_file_sha256",
    "scan_dataset",
    "guard_verified_status",
    "simulate_attack",
    "verify_file_integrity",
    "register_model",
    "verify_model",
    "snapshot_pipeline",
    "detect_code_drift",
    "reproducibility_replay",
]
