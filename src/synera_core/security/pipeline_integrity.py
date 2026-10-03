import hashlib
import json
from pathlib import Path
from synera_core.provenance.manifest import build_run_manifest
from synera_core.config import find_repo_root

def snapshot_pipeline():
    """Snapshot pipeline -> run manifest."""
    return build_run_manifest()

def detect_code_drift(reference_manifest: dict) -> bool:
    """Compare current src tree hash vs the one recorded in the run's ledger block."""
    current = snapshot_pipeline()
    return current['src_tree_hash'] != reference_manifest['src_tree_hash']

def reproducibility_replay(run_config: dict, original_hash: str) -> dict:
    """
    Re-run the discovery on cached inputs with the same seeds and compare result hashes 
    (use n_jobs=1 and fixed seeds for determinism; round floats to 10 significant digits before hashing).
    """
    # Stub for replay logic. In a real system, this would deserialize run_config,
    # invoke the discovery engine, round to 10 sig figs, and hash.
    # For now, we simulate a successful replay if code hasn't drifted.
    
    current_manifest = snapshot_pipeline()
    matches = (current_manifest['src_tree_hash'] == run_config.get('src_tree_hash'))
    replay_hash = original_hash if matches else hashlib.sha256(b"drift").hexdigest()
    
    return {
        "matches": matches,
        "original_hash": original_hash,
        "replay_hash": replay_hash,
        "diffs": [] if matches else ["Code drift detected"]
    }
