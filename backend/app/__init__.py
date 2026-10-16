"""SYNERA Backend Application Package.

Makes the API start the same way from anywhere, so ``uvicorn app.main:app`` (run inside ``backend/``) and
``uvicorn backend.app.main:app`` (run from the repository root) both work, and fails with a readable message,
not a traceback, when started with a Python that does not have the project's packages (e.g. a global install
instead of ``.venv``).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_REQUIRED = ("fastapi", "sqlmodel", "pandas", "cryptography", "synera_core")
_missing = []
for _m in _REQUIRED:
    try:
        __import__(_m)
    except ImportError:
        _missing.append(_m)
if _missing:
    raise SystemExit(
        f"\nSYNERA API cannot start: this Python ({sys.executable}) is missing {', '.join(_missing)}.\n"
        f"Use the project's virtual environment instead, from {_ROOT}:\n\n"
        "    .venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --reload     (Windows)\n"
        "    .venv/bin/python -m uvicorn backend.app.main:app --reload             (macOS/Linux)\n\n"
        "or simply run  dev.cmd  (Windows)  /  make demo.\n"
    )
