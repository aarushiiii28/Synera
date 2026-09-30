"""Finding lifecycle states and pipeline execution stages.

Finding Lifecycle:
  CANDIDATE -> VALIDATED (stats pass) -> VERIFIED (replicated + security CLEAN +
  ledger chain valid + reproducibility replay matches).
  BLOCKED = any integrity failure ("result blocked from verified status").
  REJECTED = failed stats or replication.

NOTE: VERIFIED means "statistically validated with verified computational provenance".
It NEVER means "biologically proven".
"""

from __future__ import annotations

from enum import Enum


class FindingState(str, Enum):
    """Lifecycle state of an interaction finding."""

    CANDIDATE = "CANDIDATE"      # Initial discovery hypothesis
    VALIDATED = "VALIDATED"      # Passed multiple testing & statistical thresholds
    VERIFIED = "VERIFIED"        # Statistically validated with verified computational provenance
    BLOCKED = "BLOCKED"          # Integrity / poisoning / security check failed
    REJECTED = "REJECTED"        # Failed statistical significance or replication


class PipelineStage(str, Enum):
    """Execution stages of the SYNERA pipeline orchestrator."""

    INITIALIZED = "INITIALIZED"
    DATA_INGESTED = "DATA_INGESTED"
    DISCOVERY_COMPLETED = "DISCOVERY_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    SECURITY_VERIFIED = "SECURITY_VERIFIED"
    LEDGER_RECORDED = "LEDGER_RECORDED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
