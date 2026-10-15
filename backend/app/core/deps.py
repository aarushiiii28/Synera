"""Shared FastAPI dependencies. Tests override these to use temporary databases and ledgers."""

from __future__ import annotations

import json
from typing import Any

from synera_core.provenance.ledger import Ledger
from synera_core.provenance.store import open_ledger

from backend.app.core.config import RESULTS_DIR


def get_ledger() -> Ledger:
    """The project ledger. The API only ever reads it; appends happen in the pipeline."""
    return open_ledger()


def read_result_json(name: str) -> Any | None:
    """Load ``artifacts/results/<name>`` (written by the build scripts); ``None`` if it does not exist."""
    p = RESULTS_DIR / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
