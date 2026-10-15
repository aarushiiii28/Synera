"""Single access point for the provenance ledger and repo-relative artifact paths.

Everything (data pipeline, orchestrator, API) opens the ledger through :func:`open_ledger` so there is
exactly one chain, at ``artifacts/ledger.db``, signed with the key in ``artifacts/keys`` (never committed).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from synera_core.config import find_repo_root, get_settings
from synera_core.provenance.ledger import Ledger


def repo_root() -> Path:
    return find_repo_root()


def repo_relative(path: str | Path) -> str:
    """POSIX path relative to the repo root when possible (portable manifests), else absolute POSIX."""
    p = Path(path)
    try:
        return p.resolve().relative_to(repo_root().resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def resolve_repo_path(path: str | Path) -> Path:
    """Inverse of :func:`repo_relative`."""
    p = Path(path)
    return p if p.is_absolute() else repo_root() / p


def ledger_paths() -> tuple[Path, Path]:
    s = get_settings()
    return s.resolve_path(s.ledger.db), s.resolve_path(s.ledger.key)


@lru_cache(maxsize=1)
def open_ledger() -> Ledger:
    """The project ledger (created with a fresh genesis block and key on first use)."""
    db, key = ledger_paths()
    db.parent.mkdir(parents=True, exist_ok=True)
    key.parent.mkdir(parents=True, exist_ok=True)
    return Ledger(db, key)
