"""Shared FastAPI dependencies. Tests override these to use temporary databases and ledgers."""

from __future__ import annotations

import json
import os
from typing import Any

from synera_core.config import find_repo_root
from synera_core.iot.bridge import SerialBridge
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.store import open_ledger

from backend.app.core.config import RESULTS_DIR


def get_ledger() -> Ledger:
    """The project ledger. The API only ever reads it; appends happen in the pipeline."""
    return open_ledger()


_bridge: SerialBridge | None = None


def get_bridge() -> SerialBridge:
    """The one serial bridge of this API process (a computer has one Arduino on one COM port). Tests override this dependency."""
    global _bridge
    if _bridge is None:
        _bridge = SerialBridge(find_repo_root() / "data" / "live", warmup_s=float(os.environ.get("SYNERA_GAS_WARMUP_S", "120")))
    return _bridge


def read_result_json(name: str) -> Any | None:
    """Load ``artifacts/results/<name>`` (written by the build scripts); ``None`` if it does not exist."""
    p = RESULTS_DIR / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
