"""SYNERA pipeline orchestrator coordinating the 7 architectural layers."""

from __future__ import annotations

from typing import Dict, Any, List
from synera_core.config import Settings, get_settings
from synera_core.pipeline.states import FindingState, PipelineStage


class PipelineOrchestrator:
    """Orchestrates end-to-end data ingestion, discovery, validation, security, and ledger recording."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.history: List[Dict[str, Any]] = []
        self.current_stage = PipelineStage.INITIALIZED

    def record_stage(self, stage: PipelineStage, details: Dict[str, Any] | None = None) -> None:
        """Log a pipeline stage progression event."""
        self.current_stage = stage
        self.history.append({
            "stage": stage.value,
            "details": details or {},
        })
