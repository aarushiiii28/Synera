"""Cybersecurity and data integrity subpackage."""

from synera_core.security.integrity import (
    IntegrityGuard,
    IntegrityResult,
    compute_file_sha256,
    guard_verified_status,
    verify_file_integrity,
)
from synera_core.security.model_verify import verify_model_artifact
from synera_core.security.pipeline_integrity import verify_stage_transitions
from synera_core.security.poisoning import detect_poisoning_candidates
from synera_core.security.tamper_sim import simulate_bit_flip

__all__ = [
    "compute_file_sha256",
    "verify_file_integrity",
    "IntegrityResult",
    "IntegrityGuard",
    "guard_verified_status",
    "detect_poisoning_candidates",
    "verify_model_artifact",
    "verify_stage_transitions",
    "simulate_bit_flip",
]
