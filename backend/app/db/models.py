"""Application database (SQLite). The evidence ledger is a separate database and is never written through here."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

SCHEMA_VERSION = 2


class SchemaVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    version: int = Field(default=SCHEMA_VERSION)


class Dataset(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    track: str
    kind: str
    provenance: str
    hash: str = ""
    features_count: int = 0
    samples_count: int = 0
    description: str = ""
    role: str = ""
    runnable: bool = False
    path: str = ""
    created_at: float = 0.0
    summary: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    qc: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    ledger_block: Optional[int] = None


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(index=True)
    status: str                       # RUNNING | COMPLETED | BLOCKED | FAILED
    created_at: float
    finished_at: Optional[float] = None
    config_hash: str = ""
    dataset_hash: str = ""
    result_hash: Optional[str] = None
    ledger_block: Optional[int] = None
    src_tree_hash: Optional[str] = None
    runtime_s: Optional[float] = None
    error: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    summary: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    stage_counts: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    security: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    replay: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    consistency: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    pairs: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))


class RunEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step: int
    step_name: str
    label: str = ""
    status: str
    progress: float
    message: str
    duration_s: Optional[float] = None
    ts: float
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Finding(SQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    dataset_id: str = Field(index=True)
    track: str
    provenance: str
    evidence_level: str
    stressor_a: str
    stressor_b: str
    feature: Optional[str] = None
    interaction_type: str
    status: str = Field(index=True)
    q_value: float
    effect_size: float
    created_at: float = 0.0
    effect: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    stats: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    methods: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    replication: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    security: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    surface: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    gates: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    history: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    dataset_hashes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    config: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class SecurityReport(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(index=True)
    run_id: Optional[str] = None
    status: str = "CLEAN"
    created_at: float = 0.0
    false_alarm_rates: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    checks: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


class ExperimentSummary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    dataset_id: str = ""
    config_hash: str
    result_hash: str
    status: str
    ledger_block: Optional[int] = None
    runtime_s: Optional[float] = None
    created_at: float = 0.0
