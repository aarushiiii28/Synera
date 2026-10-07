import json
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from datetime import datetime

class SchemaVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    version: int = Field(default=1)

class Dataset(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    provenance: str
    hash: str
    features_count: int
    samples_count: int
    created_at: float

class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(index=True)
    status: str
    created_at: float

class RunEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step: int
    status: str
    progress: float
    message: str
    ts: float

class Finding(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(index=True)
    v1: str
    v2: str
    interaction_type: str
    status: str
    provenance: str
    q_value: float
    effect_size: float
    
    stats: dict = Field(default_factory=dict, sa_column=Column(JSON))
    methods: dict = Field(default_factory=dict, sa_column=Column(JSON))
    replication: dict = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: dict = Field(default_factory=dict, sa_column=Column(JSON))
    history: list = Field(default_factory=list, sa_column=Column(JSON))

class SecurityReport(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str
    false_alarm_rates: dict = Field(default_factory=dict, sa_column=Column(JSON))
    checks: list = Field(default_factory=list, sa_column=Column(JSON))

class ExperimentSummary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str
    config_hash: str
    result_hash: str
    status: str
