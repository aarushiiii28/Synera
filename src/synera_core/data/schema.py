"""Data schemas and type definitions for dataset harmonization."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DatasetTrack(str, Enum):
    """Data track taxonomy."""

    TRACK_A = "A"  # Space Biology Testbed (REAL)
    TRACK_B = "B"  # Engine Benchmark (SIMULATED)
    TRACK_C = "C"  # Climate-Health (REAL, optional)


class ProvenanceType(str, Enum):
    """Data provenance classification."""

    REAL = "REAL"
    SIMULATED = "SIMULATED"


class ExperimentalDesign(str, Enum):
    """Experimental design classification."""

    FACTORIAL = "factorial"
    CONTINUOUS = "continuous"


class DatasetEntry(BaseModel):
    """Registry entry representing an ingested or reference dataset."""

    id: str
    track: DatasetTrack
    title: str
    source: str
    provenance: ProvenanceType
    files: list[str] = Field(default_factory=list)
    design: ExperimentalDesign
    stressors: list[str]
    outcome: str
    status: str = "REGISTERED"
    metadata: dict[str, Any] = Field(default_factory=dict)
