"""Backend configuration (environment-driven, no secrets in code)."""

from __future__ import annotations

import os
from pathlib import Path

from synera_core.config import find_repo_root

ROOT_DIR: Path = find_repo_root()
RESULTS_DIR: Path = ROOT_DIR / "artifacts" / "results"
DB_PATH: Path = Path(os.environ.get("SYNERA_DB_PATH", ROOT_DIR / "artifacts" / "synera.db"))
API_VERSION = "1.0.0"

# Max values accepted from clients (input validation limits)
MAX_N_BOOT = 999
MIN_N_BOOT = 49
MAX_CONCURRENT_RUNS = 2
SIMULATE_RATE_LIMIT_PER_MIN = 20


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


def offline() -> bool:
    return os.environ.get("SYNERA_OFFLINE", "0") == "1"
