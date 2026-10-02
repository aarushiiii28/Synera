"""Pipeline execution state and computational chain of custody verification."""

from __future__ import annotations

from typing import Any


def verify_stage_transitions(
    recorded_stages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify that execution pipeline stages followed permissible sequential state transitions.

    Args:
        recorded_stages: List of stage metadata dictionaries in execution order.

    Returns:
        Dictionary reporting integrity status and any anomalous transitions.
    """
    valid_transitions = {
        "INITIALIZED": ["DATA_INGESTED", "FAILED"],
        "DATA_INGESTED": ["DISCOVERY_COMPLETED", "FAILED"],
        "DISCOVERY_COMPLETED": ["VALIDATION_COMPLETED", "FAILED"],
        "VALIDATION_COMPLETED": ["SECURITY_VERIFIED", "BLOCKED", "FAILED"],
        "SECURITY_VERIFIED": ["LEDGER_RECORDED", "FAILED"],
        "LEDGER_RECORDED": ["COMPLETED"],
    }

    current = "INITIALIZED"
    for stage in recorded_stages:
        stage_name = stage.get("stage")
        if not stage_name:
            return {"valid": False, "reason": "Stage entry missing name"}
        allowed = valid_transitions.get(current, [])
        if stage_name not in allowed:
            return {
                "valid": False,
                "reason": f"Illegal transition from {current} to {stage_name}",
            }
        current = stage_name

    return {"valid": True, "final_stage": current}
