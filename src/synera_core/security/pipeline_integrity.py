"""Pipeline integrity: code drift detection and genuine reproducibility replay.

* ``snapshot_pipeline`` fingerprints the source tree, configs and environment (the run manifest).
* ``detect_code_drift`` compares the *current* source-tree hash with the one recorded for a run.
* ``reproducibility_replay`` re-executes an analysis callable and compares the digest of its outputs with
  the original. Nothing is simulated: if the code or an input changed, or the computation is not
  deterministic, the digests differ and the replay reports a mismatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from synera_core.config import find_repo_root
from synera_core.provenance.manifest import _hash_directory_tree, build_run_manifest


def current_src_tree_hash(repo_root: Path | None = None) -> str:
    root = repo_root or find_repo_root()
    return _hash_directory_tree(root / "src" / "synera_core")


def snapshot_pipeline(config: dict[str, Any] | None = None, dataset_hashes: dict | None = None,
                      seed: int | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    """Run manifest of the code, configs and environment as they are right now."""
    return build_run_manifest(config=config or {}, dataset_hashes=dataset_hashes or {}, model_hashes={},
                              seed=seed, repo_root=repo_root or find_repo_root())


def detect_code_drift(reference_manifest: dict[str, Any], repo_root: Path | None = None) -> bool:
    """True if the source tree changed since ``reference_manifest`` was recorded."""
    return current_src_tree_hash(repo_root) != reference_manifest["src_tree_hash"]


def reproducibility_replay(replay_fn: Callable[[], str], original_digest: str) -> dict[str, Any]:
    """Execute ``replay_fn`` (returns the digest of a fresh run) and compare with ``original_digest``."""
    replay_digest = replay_fn()
    matches = replay_digest == original_digest
    return {"matches": matches, "original_hash": original_digest, "replay_hash": replay_digest,
            "diffs": [] if matches else ["result digests differ"]}
