"""Typed configuration loader using pydantic-settings and YAML.

Provides repository root detection, schema validation, and cached settings access.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_repo_root(start_path: Path | None = None) -> Path:
    """Detect repository root by traversing upward for marker files."""
    current = (start_path or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for parent in [current, *current.parents]:
        if (parent / "configs" / "settings.yaml").exists() or (parent / "pyproject.toml").exists():
            return parent
    return current


class SeedsConfig(BaseModel):
    """Random seed configurations for deterministic reproducibility."""

    global_seed: int = Field(default=20260929, alias="global")


class ConfidenceWeightsConfig(BaseModel):
    """Weighting components for composite confidence score evaluation."""

    stat: float = Field(default=0.35, ge=0.0, le=1.0)
    replication: float = Field(default=0.30, ge=0.0, le=1.0)
    robustness: float = Field(default=0.20, ge=0.0, le=1.0)
    trust: float = Field(default=0.15, ge=0.0, le=1.0)


class PathsConfig(BaseModel):
    """Relative paths for datasets, artifacts, and outputs."""

    data_dir: str = "data"
    raw_data_dir: str = "data/raw"
    interim_data_dir: str = "data/interim"
    processed_data_dir: str = "data/processed"
    synthetic_data_dir: str = "data/synthetic"
    reference_data_dir: str = "data/reference"
    manifest_path: str = "data/MANIFEST.json"
    artifacts_dir: str = "artifacts"
    models_dir: str = "artifacts/models"
    results_dir: str = "artifacts/results"
    reports_dir: str = "artifacts/reports"
    keys_dir: str = "artifacts/keys"


class LedgerConfig(BaseModel):
    """Cryptographic provenance ledger storage and signing key paths."""

    db: str = "artifacts/ledger.db"
    key: str = "artifacts/keys/ledger_ed25519.pem"


class Settings(BaseSettings):
    """Global configuration settings for SYNERA core pipelines."""

    model_config = SettingsConfigDict(
        env_prefix="SYNERA_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    seeds: SeedsConfig = Field(default_factory=SeedsConfig)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    fdr_method: str = Field(default="bh")
    min_abs_effect: float = Field(default=0.5, description="log2 scale effect size threshold")
    bootstrap_reps: int = Field(default=2000, gt=0)
    cv_folds: int = Field(default=5, gt=1)
    max_findings_per_run: int = Field(default=50, gt=0)
    confidence_weights: ConfidenceWeightsConfig = Field(default_factory=ConfidenceWeightsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    ledger: LedgerConfig = Field(default_factory=LedgerConfig)
    repo_root: Path = Field(default_factory=find_repo_root)

    def resolve_path(self, relative_path: str | Path) -> Path:
        """Resolve a relative path against the repository root."""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (self.repo_root / path).resolve()


@lru_cache(maxsize=1)
def get_settings(config_path: Path | str | None = None) -> Settings:
    """Load configuration from settings.yaml with environment overrides and caching."""
    repo_root = find_repo_root()
    if config_path is None:
        yaml_file = repo_root / "configs" / "settings.yaml"
    else:
        yaml_file = Path(config_path)
        if not yaml_file.is_absolute():
            yaml_file = (repo_root / yaml_file).resolve()

    yaml_data: dict[str, Any] = {}
    if yaml_file.exists():
        with open(yaml_file, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                yaml_data = loaded

    settings = Settings(**yaml_data, repo_root=repo_root)
    return settings
